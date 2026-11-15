import asyncio
import socket
import time
import zlib
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit

import aiohttp
from aiohttp.abc import AbstractResolver
from aiohttp.resolver import ThreadedResolver
from protego import Protego

from crawler_poc.config import Settings
from crawler_poc.models import Outcome, is_public_address, normalize_url, origin_of


class FetchError(Exception):
    def __init__(
        self,
        outcome: Outcome,
        reason: str,
        *,
        retryable: bool = False,
        retry_after: float = 0,
        http_status: int | None = None,
        url: str | None = None,
        content_type: str | None = None,
        stage: str = "fetch",
        limit_bytes: int | None = None,
        observed_bytes: int | None = None,
        details: dict[str, str] | None = None,
    ) -> None:
        super().__init__(reason)
        self.outcome = outcome
        self.reason = reason
        self.retryable = retryable
        self.retry_after = retry_after
        self.http_status, self.url, self.content_type = http_status, url, content_type
        self.stage, self.limit_bytes, self.observed_bytes = stage, limit_bytes, observed_bytes
        self.details = details or {}

    def as_result(self) -> dict[str, Any]:
        metadata = {**self.details, "failure_stage": self.stage}
        if self.url:
            parts = urlsplit(self.url)
            metadata["failure_url"] = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        for key, value in (
            ("failure_limit_bytes", self.limit_bytes),
            ("failure_observed_bytes", self.observed_bytes),
        ):
            if value is not None:
                metadata[key] = str(value)
        return {
            "outcome": self.outcome.value,
            "reason": self.reason,
            "http_status": self.http_status,
            "final_url": self.url if self.stage != "robots" and self.http_status else None,
            "content_type": self.content_type,
            "metadata": metadata,
        }


def retry_after_seconds(value: str) -> float:
    value = value.strip()
    try:
        delay = (
            float(value)
            if value.isdigit()
            else parsedate_to_datetime(value).timestamp() - time.time()
        )
    except (ValueError, TypeError, OverflowError):
        return 0
    return max(0, min(60, delay))


class OriginGate(Protocol):
    def slot(self, origin: str) -> Any: ...


class GuardedResolver(AbstractResolver):
    def __init__(self, delegate: AbstractResolver | None = None) -> None:
        self.delegate = delegate or ThreadedResolver()

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[Any]:
        answers = await self.delegate.resolve(host, port, family)
        if not answers or any(not is_public_address(item["host"]) for item in answers):
            raise FetchError(Outcome.POLICY_BLOCKED, "dns_destination_forbidden")
        return answers

    async def close(self) -> None:
        await self.delegate.close()


class LocalOriginGate:
    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.lock = asyncio.Lock()
        self.next_at: dict[str, float] = {}

    @asynccontextmanager
    async def slot(self, origin: str) -> AsyncIterator[None]:
        async with self.lock:
            now = time.monotonic()
            when = max(now, self.next_at.get(origin, now))
            self.next_at[origin] = when + self.delay
            if len(self.next_at) > 4096:
                self.next_at = {key: value for key, value in self.next_at.items() if value > now}
        await asyncio.sleep(max(0, when - time.monotonic()))
        yield


@dataclass
class RawResponse:
    status: int
    headers: dict[str, str]
    body: bytes


def response_error(
    response: RawResponse,
    url: str,
    outcome: Outcome,
    reason: str,
    *,
    stage: str = "fetch",
    retryable: bool = False,
) -> FetchError:
    return FetchError(
        outcome,
        reason,
        http_status=response.status,
        url=url,
        content_type=response.headers.get("content-type", "").split(";")[0].lower(),
        stage=stage,
        retryable=retryable,
        retry_after=retry_after_seconds(response.headers.get("retry-after", ""))
        if retryable
        else 0,
    )


@dataclass
class FetchedPage:
    final_url: str
    body: bytes
    http_status: int
    content_type: str
    fetch_method: str = "http"
    headers: dict[str, str] = field(default_factory=dict)


class SafeFetcher:
    def __init__(self, settings: Settings, gate: OriginGate | None = None) -> None:
        self.settings = settings
        self.gate = gate or LocalOriginGate(settings.origin_delay)
        self.session: aiohttp.ClientSession | None = None
        self.robots: OrderedDict[str, tuple[float, Any, int, str, str]] = OrderedDict()

    async def __aenter__(self) -> "SafeFetcher":
        connector = aiohttp.TCPConnector(
            resolver=GuardedResolver(),
            limit=self.settings.workers,
            limit_per_host=1,
            use_dns_cache=False,
        )
        self.session = aiohttp.ClientSession(
            connector=connector,
            trust_env=False,
            cookie_jar=aiohttp.DummyCookieJar(),
            auto_decompress=False,
            timeout=aiohttp.ClientTimeout(
                total=self.settings.request_timeout, connect=min(5, self.settings.request_timeout)
            ),
            headers={
                "User-Agent": self.settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
            },
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self.session:
            await self.session.close()

    async def _request(self, url: str, limit: int) -> RawResponse:
        try:
            url = normalize_url(url)
        except ValueError as exc:
            raise FetchError(Outcome.POLICY_BLOCKED, "destination_forbidden") from exc
        assert self.session is not None
        async with self.gate.slot(origin_of(url)):
            async with self.session.get(url, allow_redirects=False) as response:
                headers = {key.lower(): value for key, value in response.headers.items()}
                if response.status != 200:
                    return RawResponse(response.status, headers, b"")
                try:
                    body = await self._read_body(response, limit)
                except FetchError as exc:
                    exc.http_status, exc.url = response.status, url
                    exc.content_type = headers.get("content-type", "").split(";")[0].lower()
                    raise
                except zlib.error as exc:
                    raise FetchError(
                        Outcome.UNSUPPORTED,
                        "invalid_compressed_body",
                        http_status=response.status,
                        url=url,
                        content_type=headers.get("content-type", "").split(";")[0].lower(),
                    ) from exc
                except (aiohttp.ClientError, TimeoutError, OSError) as exc:
                    raise FetchError(
                        Outcome.RETRY_EXHAUSTED,
                        "network_or_timeout",
                        retryable=True,
                        http_status=response.status,
                        url=url,
                        content_type=headers.get("content-type", "").split(";")[0].lower(),
                    ) from exc
                return RawResponse(response.status, headers, body)

    async def _read_body(self, response: aiohttp.ClientResponse, limit: int) -> bytes:
        headers = {key.lower(): value for key, value in response.headers.items()}
        encoding = headers.get("content-encoding", "").lower()
        decompressor = None
        if encoding == "gzip":
            decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        elif encoding == "deflate":
            decompressor = zlib.decompressobj()
        elif encoding not in {"", "identity"}:
            raise FetchError(Outcome.UNSUPPORTED, "unsupported_content_encoding")
        data = bytearray()
        wire_bytes = 0
        wire_limit = min(limit, self.settings.max_wire_bytes)
        async for chunk in response.content.iter_chunked(16384):
            wire_bytes += len(chunk)
            if wire_bytes > wire_limit:
                raise FetchError(
                    Outcome.TOO_LARGE,
                    "wire_size_limit",
                    limit_bytes=wire_limit,
                    observed_bytes=wire_bytes,
                )
            decoded = (
                decompressor.decompress(chunk, max(1, limit + 1 - len(data)))
                if decompressor
                else chunk
            )
            data.extend(decoded)
            if len(data) > limit or (decompressor and decompressor.unconsumed_tail):
                raise FetchError(
                    Outcome.TOO_LARGE,
                    "decoded_size_limit",
                    limit_bytes=limit,
                    observed_bytes=len(data),
                )
        if decompressor and not decompressor.eof:
            raise FetchError(Outcome.UNSUPPORTED, "invalid_compressed_body")
        if decompressor and decompressor.unused_data:
            raise FetchError(Outcome.UNSUPPORTED, "trailing_compressed_data")
        return bytes(data)

    async def _robots_allowed(self, url: str) -> None:
        origin = origin_of(url)
        now = time.monotonic()
        cached = self.robots.get(origin)
        if cached and cached[0] > now:
            _, rule, status, policy_url, content_type = cached
            self.robots.move_to_end(origin)
        else:
            target = origin + "/robots.txt"
            for _ in range(6):
                requested_url = target
                try:
                    response = await self._request(target, 512 * 1024)
                except FetchError as exc:
                    exc.stage = "robots"
                    exc.url = exc.url or target
                    if exc.outcome == Outcome.POLICY_BLOCKED:
                        raise
                    raise FetchError(
                        Outcome.ROBOTS_UNAVAILABLE,
                        "robots_fetch_failed",
                        retryable=exc.retryable,
                        stage="robots",
                        http_status=exc.http_status,
                        url=exc.url or target,
                        content_type=exc.content_type,
                        limit_bytes=exc.limit_bytes,
                        observed_bytes=exc.observed_bytes,
                    ) from exc
                except (aiohttp.ClientError, TimeoutError, OSError, zlib.error) as exc:
                    raise FetchError(
                        Outcome.ROBOTS_UNAVAILABLE,
                        "robots_network_or_timeout",
                        retryable=True,
                        stage="robots",
                        url=target,
                    ) from exc
                if response.status in {301, 302, 303, 307, 308}:
                    target = normalize_url(urljoin(target, response.headers.get("location", "")))
                    continue
                break
            else:
                raise response_error(
                    response,
                    requested_url,
                    Outcome.ROBOTS_UNAVAILABLE,
                    "robots_redirect_limit",
                    stage="robots",
                )
            if response.status == 429 or response.status >= 500:
                raise response_error(
                    response,
                    target,
                    Outcome.ROBOTS_UNAVAILABLE,
                    "robots_unavailable",
                    stage="robots",
                    retryable=True,
                )
            elif 400 <= response.status < 500:
                rule = True
            elif response.status == 200:
                rule = Protego.parse(response.body.decode("utf-8", errors="replace"))
            else:
                raise response_error(
                    response,
                    target,
                    Outcome.ROBOTS_UNAVAILABLE,
                    "robots_unexpected_status",
                    stage="robots",
                )
            status, policy_url = response.status, target
            content_type = response.headers.get("content-type", "").split(";")[0].lower()
            self.robots[origin] = (now + 3600, rule, status, policy_url, content_type)
            if len(self.robots) > 1000:
                self.robots.popitem(last=False)
        agent = self.settings.user_agent.partition("/")[0].split()[0]
        allowed = rule if isinstance(rule, bool) else rule.can_fetch(url, agent)
        if not allowed:
            raise FetchError(
                Outcome.ROBOTS_DISALLOWED,
                "robots_disallowed",
                stage="robots",
                http_status=status,
                url=policy_url,
                content_type=content_type,
            )

    async def fetch(
        self, url: str, *, html_only: bool = True, max_bytes: int | None = None
    ) -> FetchedPage:
        stage = "robots"
        try:
            async with asyncio.timeout(self.settings.request_timeout):
                target = normalize_url(url)
                for _ in range(6):
                    stage = "robots"
                    await self._robots_allowed(target)
                    stage = "fetch"
                    requested_url = target
                    response = await self._request(
                        target, min(self.settings.max_bytes, max_bytes or self.settings.max_bytes)
                    )
                    if response.status in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise response_error(
                                response, target, Outcome.UNSUPPORTED, "redirect_without_location"
                            )
                        target = normalize_url(urljoin(target, location))
                        continue
                    if response.status == 429 or response.status >= 500:
                        raise response_error(
                            response,
                            target,
                            Outcome.RETRY_EXHAUSTED,
                            "transient_http_status",
                            retryable=True,
                        )
                    if response.status in {401, 403}:
                        raise response_error(
                            response, target, Outcome.TARGET_BLOCKED, "target_access_denied"
                        )
                    if response.status in {404, 410}:
                        raise response_error(
                            response, target, Outcome.NOT_FOUND, "target_not_found"
                        )
                    if response.status != 200:
                        raise response_error(
                            response, target, Outcome.UNSUPPORTED, "unsupported_http_status"
                        )
                    content_type = response.headers.get("content-type", "").split(";")[0].lower()
                    if html_only and content_type not in {"text/html", "application/xhtml+xml"}:
                        raise response_error(response, target, Outcome.UNSUPPORTED, "not_html")
                    return FetchedPage(
                        target,
                        response.body,
                        response.status,
                        content_type,
                        headers=response.headers,
                    )
                raise response_error(response, requested_url, Outcome.UNSUPPORTED, "redirect_limit")
        except FetchError:
            raise
        except ValueError as exc:
            raise FetchError(Outcome.POLICY_BLOCKED, "redirect_destination_forbidden") from exc
        except (aiohttp.ClientError, TimeoutError, OSError) as exc:
            raise FetchError(
                Outcome.RETRY_EXHAUSTED,
                "network_or_timeout",
                retryable=True,
                stage=stage,
                url=target if stage == "fetch" else origin_of(target) + "/robots.txt",
            ) from exc
        except zlib.error as exc:
            raise FetchError(Outcome.UNSUPPORTED, "invalid_compressed_body") from exc
