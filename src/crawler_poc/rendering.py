import asyncio
import contextlib
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

from crawler_poc.config import Settings
from crawler_poc.fetching import FetchedPage, FetchError, GuardedResolver, SafeFetcher
from crawler_poc.models import Outcome, normalize_url


@asynccontextmanager
async def deny_browser_egress() -> AsyncIterator[int]:
    async def reject(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()

    server = await asyncio.start_server(reject, "127.0.0.1", 0)
    try:
        yield server.sockets[0].getsockname()[1]
    finally:
        server.close()
        await server.wait_closed()


def _launch_channel(channel: str) -> str | None:
    return None if channel == "chromium" else channel


class BrowserRenderer:
    """Execute a JS shell, fulfilling every network request through SafeFetcher."""

    def __init__(self, settings: Settings, fetcher: SafeFetcher) -> None:
        self.settings, self.fetcher = settings, fetcher
        self.slot = asyncio.Semaphore(1)

    async def render(self, initial: FetchedPage) -> tuple[FetchedPage, dict[str, str]]:
        try:
            from playwright.async_api import Error as BrowserError
            from playwright.async_api import TimeoutError as BrowserTimeout
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise FetchError(
                Outcome.UNSUPPORTED, "browser_runtime_unavailable", stage="render"
            ) from exc

        failure: FetchError | None = None
        served_bytes, requests, blocked = len(initial.body), 0, 0
        initial_served = False
        browser: Any = None
        environment: dict[str, str | float | bool] = {
            key: value
            for key, value in os.environ.items()
            if key.upper()
            in {
                "PATH",
                "SYSTEMROOT",
                "WINDIR",
                "TEMP",
                "TMP",
                "HOME",
                "USERPROFILE",
                "LOCALAPPDATA",
                "LANG",
                "LC_ALL",
                "PLAYWRIGHT_BROWSERS_PATH",
            }
        }
        try:
            async with asyncio.timeout(self.settings.request_timeout):
                async with self.slot, deny_browser_egress() as port, async_playwright() as runtime:
                    browser = await runtime.chromium.launch(
                        channel=_launch_channel(self.settings.browser_channel),
                        headless=True,
                        chromium_sandbox=self.settings.browser_sandbox,
                        env=environment,
                        proxy={"server": f"http://127.0.0.1:{port}"},
                        args=[
                            "--proxy-bypass-list=<-loopback>",
                            "--host-resolver-rules=MAP * ~NOTFOUND",
                            "--disable-quic",
                            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                            "--disable-dev-shm-usage",
                        ],
                    )
                    context = await browser.new_context(
                        accept_downloads=False,
                        ignore_https_errors=False,
                        service_workers="block",
                    )
                    page = await context.new_page()
                    await context.add_init_script(
                        "for (const name of ['Worker', 'SharedWorker', 'WebSocket', "
                        "'WebTransport', 'RTCPeerConnection', 'webkitRTCPeerConnection']) "
                        "Object.defineProperty(globalThis, name, {value: undefined});"
                    )

                    async def route_request(route: Any) -> None:
                        nonlocal failure, served_bytes, requests, blocked, initial_served
                        request = route.request
                        if failure is not None:
                            await route.abort()
                            return
                        try:
                            requests += 1
                            if requests > self.settings.browser_max_requests:
                                raise FetchError(
                                    Outcome.TOO_LARGE, "browser_request_limit", stage="render"
                                )
                            if (
                                request.method != "GET"
                                or request.resource_type
                                not in {"document", "script", "stylesheet", "xhr", "fetch"}
                                or request.frame != page.main_frame
                            ):
                                blocked += 1
                                await route.abort()
                                return
                            url = normalize_url(request.url)
                            if not initial_served and request.is_navigation_request():
                                if url != normalize_url(initial.final_url):
                                    raise FetchError(
                                        Outcome.POLICY_BLOCKED,
                                        "browser_initial_destination_changed",
                                        stage="render",
                                    )
                                resource = initial
                                initial_served = True
                            else:
                                if request.is_navigation_request():
                                    raise FetchError(
                                        Outcome.UNSUPPORTED,
                                        "browser_navigation_changed",
                                        stage="render",
                                    )
                                remaining = self.settings.max_bytes - served_bytes
                                if remaining <= 0:
                                    raise FetchError(
                                        Outcome.TOO_LARGE,
                                        "browser_resource_size_limit",
                                        stage="render",
                                    )
                                resource = await self.fetcher.fetch(
                                    url, html_only=False, max_bytes=remaining
                                )
                                served_bytes += len(resource.body)
                                if resource.final_url != url:
                                    raise FetchError(
                                        Outcome.UNSUPPORTED,
                                        "browser_resource_redirect_unsupported",
                                        stage="render",
                                    )
                            if served_bytes > self.settings.max_bytes:
                                raise FetchError(
                                    Outcome.TOO_LARGE,
                                    "browser_resource_size_limit",
                                    stage="render",
                                )
                            headers = {
                                key: value
                                for key, value in resource.headers.items()
                                if key
                                in {
                                    "content-type",
                                    "content-security-policy",
                                    "access-control-allow-origin",
                                    "access-control-allow-credentials",
                                    "access-control-expose-headers",
                                    "content-language",
                                }
                            }
                            headers.setdefault("content-type", resource.content_type)
                            if request.is_navigation_request():
                                safety = (
                                    "worker-src 'none'; frame-src 'none'; object-src 'none'; "
                                    "form-action 'none'; connect-src http: https:"
                                )
                                headers["content-security-policy"] = ", ".join(
                                    filter(None, [headers.get("content-security-policy"), safety])
                                )
                            # Never continue/fulfill a redirect: Chromium would follow it
                            # outside the guarded Python transport.
                            await route.fulfill(status=200, headers=headers, body=resource.body)
                        except ValueError:
                            failure = FetchError(
                                Outcome.POLICY_BLOCKED,
                                "browser_destination_forbidden",
                                stage="render",
                            )
                            await route.abort()
                        except FetchError as exc:
                            failure = exc
                            await route.abort()
                        except BrowserError:
                            if not page.is_closed():
                                raise

                    await context.route("**/*", route_request)
                    try:
                        await page.goto(
                            initial.final_url,
                            wait_until="domcontentloaded",
                            timeout=self.settings.request_timeout * 1000,
                        )
                        with contextlib.suppress(BrowserTimeout):
                            await page.wait_for_function(
                                "() => document.body && document.body.innerText.length >= 40",
                                timeout=min(5000, self.settings.request_timeout * 1000),
                            )
                        with contextlib.suppress(BrowserTimeout):
                            await page.wait_for_load_state(
                                "networkidle",
                                timeout=min(5000, self.settings.request_timeout * 1000),
                            )
                        if failure is not None:
                            raise failure
                        session = await context.new_cdp_session(page)
                        frame = (await session.send("Page.getFrameTree"))["frameTree"]["frame"]
                        world = await session.send(
                            "Page.createIsolatedWorld",
                            {"frameId": frame["id"], "worldName": "crawler-snapshot"},
                        )
                        snapshot = await session.send(
                            "Runtime.evaluate",
                            {
                                "contextId": world["executionContextId"],
                                "expression": (
                                    "(() => {const s = document.documentElement.outerHTML; "
                                    f"return s.length <= {self.settings.max_bytes} ? s : null"
                                    "})()"
                                ),
                                "returnByValue": True,
                            },
                        )
                        source = snapshot["result"].get("value")
                        if not isinstance(source, str):
                            raise FetchError(
                                Outcome.TOO_LARGE, "browser_dom_size_limit", stage="render"
                            )
                        body = source.encode("utf-8")
                        if len(body) > self.settings.max_bytes:
                            raise FetchError(
                                Outcome.TOO_LARGE, "browser_dom_size_limit", stage="render"
                            )
                        return (
                            FetchedPage(
                                normalize_url(page.url),
                                body,
                                initial.http_status,
                                "text/html",
                                "headless",
                            ),
                            {
                                "render_resource_requests": str(requests),
                                "render_resource_bytes": str(served_bytes),
                                "render_blocked_requests": str(blocked),
                                "render_completeness": "best-effort",
                                "raw_representation": "rendered-dom",
                                "browser_version": browser.version,
                            },
                        )
                    finally:
                        await context.close()
                        await browser.close()
        except FetchError:
            raise
        except (BrowserTimeout, TimeoutError) as exc:
            raise failure or FetchError(
                Outcome.UNSUPPORTED, "browser_timeout", stage="render"
            ) from exc

    async def fetch_page(self, url: str) -> tuple[FetchedPage, dict[str, str]]:
        """Fetch a target URL directly via Playwright when HTTP receives 403/503."""
        try:
            from playwright.async_api import Error as BrowserError
            from playwright.async_api import TimeoutError as BrowserTimeout
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise FetchError(
                Outcome.UNSUPPORTED, "browser_runtime_unavailable", stage="render"
            ) from exc

        target = normalize_url(url)
        await self.fetcher._robots_allowed(target)
        host = str(urlsplit(target).hostname or "")
        await GuardedResolver().resolve(host, 443)

        with contextlib.suppress(Exception):
            from urllib.parse import urljoin

            from curl_cffi import requests as curl_requests

            imp_url = target
            for _ in range(6):
                parsed_imp = urlsplit(imp_url)
                await GuardedResolver().resolve(
                    str(parsed_imp.hostname or ""), parsed_imp.port or 443
                )
                imp_resp = await asyncio.to_thread(
                    curl_requests.get,
                    imp_url,
                    impersonate="chrome",
                    timeout=min(10.0, self.settings.request_timeout),
                    allow_redirects=False,
                )
                if imp_resp.status_code in {301, 302, 303, 307, 308}:
                    loc = imp_resp.headers.get("location")
                    if not loc:
                        break
                    imp_url = normalize_url(urljoin(imp_url, loc))
                    continue
                if imp_resp.status_code == 200 and len(imp_resp.content) <= self.settings.max_bytes:
                    imp_text = imp_resp.content.decode("utf-8", errors="ignore").casefold()
                    if (
                        "px-captcha" not in imp_text
                        and "access to this page has been denied" not in imp_text
                        and "robot check" not in imp_text
                    ):
                        ctype = (
                            imp_resp.headers.get("content-type", "text/html").split(";")[0].lower()
                        )
                        return (
                            FetchedPage(
                                imp_url,
                                imp_resp.content,
                                200,
                                ctype or "text/html",
                                "headless",
                            ),
                            {
                                "render_completeness": "tls-impersonated",
                                "raw_representation": "http2-chrome-impersonated",
                            },
                        )
                break

        has_display = os.name == "nt" or bool(
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
        )
        modes: tuple[bool, ...] = (True, False) if has_display else (True,)
        last_status: int | None = None
        last_url: str = target
        for headless in modes:
            failure: FetchError | None = None
            requests, blocked = 0, 0
            browser: Any = None
            args: list[str] = [
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=HttpsFirstBalancedModeAutoEnable",
                "--disable-gpu",
            ]
            if not headless:
                args.append("--window-position=-2000,-2000")
            try:
                async with asyncio.timeout(min(15.0, self.settings.request_timeout)):
                    async with self.slot, async_playwright() as runtime:
                        browser = await runtime.chromium.launch(
                            channel=_launch_channel(self.settings.browser_channel),
                            headless=headless,
                            chromium_sandbox=self.settings.browser_sandbox,
                            args=args,
                        )
                        ctx_kwargs: dict[str, Any] = {
                            "accept_downloads": False,
                            "ignore_https_errors": False,
                            "service_workers": "block",
                            "viewport": {"width": 1366, "height": 768},
                            "locale": "en-US",
                        }
                        if headless:
                            ctx_kwargs["user_agent"] = (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
                            )
                        context = await browser.new_context(**ctx_kwargs)
                        await context.add_init_script(
                            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                        )
                        page = await context.new_page()

                        async def route_guard(route: Any) -> None:
                            nonlocal failure, requests, blocked
                            req = route.request
                            if failure is not None:
                                await route.abort()
                                return
                            try:
                                normalize_url(req.url)
                            except ValueError:
                                blocked += 1
                                failure = FetchError(
                                    Outcome.POLICY_BLOCKED,
                                    "browser_destination_forbidden",
                                    stage="render",
                                )
                                await route.abort()
                                return
                            if req.resource_type in {"image", "media", "font"}:
                                blocked += 1
                                await route.abort()
                                return
                            requests += 1
                            await route.continue_()

                        await context.route("**/*", route_guard)
                        try:
                            resp = await page.goto(
                                target,
                                wait_until="commit",
                                timeout=min(8000, self.settings.request_timeout * 1000),
                            )
                            with contextlib.suppress(BrowserTimeout):
                                await page.wait_for_load_state(
                                    "domcontentloaded",
                                    timeout=min(4000, self.settings.request_timeout * 1000),
                                )
                            await page.wait_for_timeout(400)
                            if failure is not None:
                                raise failure
                            status = resp.status if resp else 200
                            source = await page.content()
                            body = source.encode("utf-8")
                            if len(body) > self.settings.max_bytes:
                                raise FetchError(
                                    Outcome.TOO_LARGE, "browser_dom_size_limit", stage="render"
                                )
                            final_url = normalize_url(page.url)
                            last_status, last_url = status, final_url
                            if (
                                headless
                                and len(modes) > 1
                                and (
                                    status in {403, 503}
                                    or "px-captcha" in source.casefold()
                                    or "access to this page has been denied" in source.casefold()
                                )
                            ):
                                continue
                            if status in {403, 503}:
                                raise FetchError(
                                    Outcome.TARGET_BLOCKED
                                    if status == 403
                                    else Outcome.RETRY_EXHAUSTED,
                                    "target_access_denied"
                                    if status == 403
                                    else "transient_http_status",
                                    http_status=status,
                                    url=final_url,
                                    content_type="text/html",
                                    stage="render",
                                )
                            return (
                                FetchedPage(
                                    final_url,
                                    body,
                                    status,
                                    "text/html",
                                    "headless",
                                ),
                                {
                                    "render_resource_requests": str(requests),
                                    "render_blocked_requests": str(blocked),
                                    "render_completeness": "best-effort",
                                    "raw_representation": "rendered-dom",
                                    "browser_version": browser.version,
                                },
                            )
                        finally:
                            await context.close()
                            await browser.close()
            except FetchError:
                raise
            except (BrowserTimeout, TimeoutError) as exc:
                if headless == modes[-1]:
                    if last_status in {401, 403, 503}:
                        raise FetchError(
                            Outcome.TARGET_BLOCKED
                            if last_status in {401, 403}
                            else Outcome.RETRY_EXHAUSTED,
                            "target_access_denied"
                            if last_status in {401, 403}
                            else "transient_http_status",
                            http_status=last_status,
                            url=last_url,
                            content_type="text/html",
                            stage="render",
                        ) from exc
                    raise failure or FetchError(
                        Outcome.UNSUPPORTED,
                        "browser_timeout",
                        stage="render",
                        details={"browser_error": type(exc).__name__},
                    ) from exc
            except BrowserError as exc:
                if headless == modes[-1]:
                    raise failure or FetchError(
                        Outcome.UNSUPPORTED,
                        "browser_runtime_or_navigation_failed",
                        stage="render",
                        details={"browser_error": str(exc)[:180]},
                    ) from exc
        raise FetchError(
            Outcome.TARGET_BLOCKED,
            "target_access_denied",
            http_status=last_status,
            url=last_url,
            content_type="text/html" if last_status else None,
            stage="render",
        )
