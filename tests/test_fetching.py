import socket
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from crawler_poc.config import Settings
from crawler_poc.fetching import FetchError, GuardedResolver, RawResponse, SafeFetcher
from crawler_poc.models import Outcome


async def test_resolver_rejects_mixed_and_rebound_addresses() -> None:
    delegate = AsyncMock()
    delegate.resolve.return_value = [{"host": "8.8.8.8"}, {"host": "127.0.0.1"}]
    resolver = GuardedResolver(delegate)
    with pytest.raises(FetchError) as error:
        await resolver.resolve("example.com", 443, socket.AF_INET)
    assert error.value.outcome == Outcome.POLICY_BLOCKED


async def test_robots_disallow_prevents_page_request() -> None:
    fetcher = SafeFetcher(Settings())
    fetcher._request = AsyncMock(  # type: ignore[method-assign]
        return_value=RawResponse(200, {}, b"User-agent: *\nDisallow: /private\n")
    )
    with pytest.raises(FetchError) as error:
        await fetcher.fetch("https://example.com/private/secret")
    assert error.value.outcome == Outcome.ROBOTS_DISALLOWED
    assert fetcher._request.await_count == 1


async def test_redirect_to_private_address_never_requested() -> None:
    fetcher = SafeFetcher(Settings())
    request = AsyncMock(
        side_effect=[
            RawResponse(404, {}, b""),
            RawResponse(302, {"location": "http://169.254.169.254/"}, b""),
        ]
    )
    fetcher._request = request  # type: ignore[method-assign]
    with pytest.raises(FetchError) as error:
        await fetcher.fetch("https://example.com/")
    assert error.value.outcome == Outcome.POLICY_BLOCKED
    assert request.await_count == 2


@pytest.mark.parametrize(
    ("status", "expected", "retryable"),
    [
        (404, Outcome.NOT_FOUND, False),
        (403, Outcome.TARGET_BLOCKED, False),
        (429, Outcome.RETRY_EXHAUSTED, True),
        (503, Outcome.RETRY_EXHAUSTED, True),
    ],
)
async def test_http_outcomes(status: int, expected: Outcome, retryable: bool) -> None:
    fetcher = SafeFetcher(Settings())
    fetcher._request = AsyncMock(  # type: ignore[method-assign]
        side_effect=[RawResponse(404, {}, b""), RawResponse(status, {}, b"")]
    )
    with pytest.raises(FetchError) as error:
        await fetcher.fetch("https://example.com/")
    assert error.value.outcome == expected
    assert error.value.retryable is retryable
    assert error.value.http_status == status
    assert error.value.as_result()["final_url"] == "https://example.com/"


@pytest.mark.parametrize("status", [401, 403, 404])
async def test_cached_robots_4xx_unavailable_allows_page_fetch_per_rfc9309(status: int) -> None:
    fetcher = SafeFetcher(Settings())
    request = AsyncMock(
        side_effect=[
            RawResponse(status, {"content-type": "text/html"}, b""),
            RawResponse(200, {"content-type": "text/html"}, b"<html><title>OK</title></html>"),
            RawResponse(200, {"content-type": "text/html"}, b"<html><title>OK2</title></html>"),
        ]
    )
    fetcher._request = request  # type: ignore[method-assign]
    for path in ("one", "two"):
        page = await fetcher.fetch(f"https://example.com/{path}")
        assert page.http_status == 200
    assert request.await_count == 3


@pytest.mark.parametrize(
    ("header", "delay"),
    [
        (format_datetime(datetime.fromtimestamp(1700000030, UTC), usegmt=True), 30),
        (format_datetime(datetime.fromtimestamp(1699999990, UTC), usegmt=True), 0),
        ("120", 60),
        ("invalid", 0),
    ],
)
async def test_retry_after_accepts_http_date_and_remains_bounded(
    monkeypatch: pytest.MonkeyPatch, header: str, delay: float
) -> None:
    monkeypatch.setattr("crawler_poc.fetching.time.time", lambda: 1700000000)
    fetcher = SafeFetcher(Settings())
    fetcher._request = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            RawResponse(404, {}, b""),
            RawResponse(503, {"retry-after": header}, b""),
        ]
    )
    with pytest.raises(FetchError) as error:
        await fetcher.fetch("https://example.com/")
    assert error.value.retry_after == delay
    assert error.value.retryable


async def test_cross_origin_redirect_checks_new_robots() -> None:
    fetcher = SafeFetcher(Settings())
    calls: list[str] = []

    async def request(url: str, limit: int) -> Any:
        calls.append(url)
        if url.endswith("/robots.txt"):
            return RawResponse(404, {}, b"")
        if "example.com" in url:
            return RawResponse(302, {"location": "https://example.org/article"}, b"")
        return RawResponse(200, {"content-type": "text/html"}, b"<html>content</html>")

    fetcher._request = request  # type: ignore[method-assign]
    result = await fetcher.fetch("https://example.com/start")
    assert result.final_url == "https://example.org/article"
    assert "https://example.org/robots.txt" in calls


async def test_robots_uses_configured_product_token_and_network_outcome() -> None:
    fetcher = SafeFetcher(Settings(user_agent="ResearchBot/1.0"))
    fetcher._request = AsyncMock(  # type: ignore[method-assign]
        return_value=RawResponse(200, {}, b"User-agent: ResearchBot\nDisallow: /\n")
    )
    with pytest.raises(FetchError) as error:
        await fetcher.fetch("https://example.com/")
    assert error.value.outcome == Outcome.ROBOTS_DISALLOWED
    fetcher.robots.clear()
    fetcher._request.side_effect = TimeoutError()
    with pytest.raises(FetchError) as error:
        await fetcher.fetch("https://example.com/")
    assert error.value.outcome == Outcome.ROBOTS_UNAVAILABLE
