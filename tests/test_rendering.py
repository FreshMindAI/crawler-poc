import asyncio
import os
from unittest.mock import AsyncMock

import pytest

from crawler_poc.config import Settings
from crawler_poc.extraction import extract_page
from crawler_poc.fetching import FetchedPage, FetchError, RawResponse, SafeFetcher
from crawler_poc.models import Outcome
from crawler_poc.rendering import BrowserRenderer, deny_browser_egress


async def test_native_browser_proxy_cannot_forward_connections() -> None:
    async with deny_browser_egress() as port:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"CONNECT 169.254.169.254:80 HTTP/1.1\r\n\r\n")
        await writer.drain()
        try:
            assert await reader.read(1024) == b""
        except ConnectionResetError:
            pass
        finally:
            writer.close()


@pytest.mark.parametrize("attack", [False, True])
@pytest.mark.browser
@pytest.mark.skipif(
    os.environ.get("CRAWLER_RUN_BROWSER_TESTS") != "1",
    reason="Explicit browser runtime test",
)
async def test_actual_js_execution_uses_guarded_python_transport(attack: bool) -> None:
    settings = Settings(browser_fallback=True)
    fetcher = SafeFetcher(settings)
    fetcher._request = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            RawResponse(404, {}, b""),
            RawResponse(
                200,
                {"content-type": "application/javascript"},
                b"document.querySelector('#app').innerHTML = "
                b"'<main><h1>Orchard field guide</h1><p>Healthy orchard trees need balanced "
                b"nutrients, compost and careful irrigation throughout every season.</p></main>';",
            )
            if not attack
            else RawResponse(302, {"location": "http://169.254.169.254/secret"}, b""),
        ]
    )
    initial = FetchedPage(
        "https://example.com/app",
        b"<html><head><title>Orchard field guide</title></head>"
        b"<body><div id='app'></div><script src='/app.js'></script></body></html>",
        200,
        "text/html",
    )
    renderer = BrowserRenderer(settings, fetcher)
    if attack:
        with pytest.raises(FetchError) as error:
            await renderer.render(initial)
        assert error.value.outcome == Outcome.POLICY_BLOCKED
    else:
        fetched, details = await renderer.render(initial)
        page = extract_page(fetched.body, fetched.final_url)
        assert "careful irrigation" in page.body
        assert fetched.fetch_method == "headless"
        assert details["render_resource_requests"] == "2"
    assert fetcher._request.await_count == 2


@pytest.mark.browser
@pytest.mark.skipif(
    os.environ.get("CRAWLER_RUN_BROWSER_TESTS") != "1",
    reason="Explicit browser runtime test",
)
async def test_browser_blocks_private_resource_before_transport() -> None:
    settings = Settings(browser_fallback=True)
    fetcher = SafeFetcher(settings)
    fetcher._request = AsyncMock()  # type: ignore[method-assign]
    initial = FetchedPage(
        "https://example.com/app",
        b"<html><body><script>"
        b"fetch('http://127.0.0.1/private').catch(() => {document.body.innerText="
        b"'A long enough fallback paragraph that must not turn a forbidden request into success.'"
        b"});</script></body></html>",
        200,
        "text/html",
    )
    with pytest.raises(FetchError) as error:
        await BrowserRenderer(settings, fetcher).render(initial)
    assert error.value.outcome == Outcome.POLICY_BLOCKED
    fetcher._request.assert_not_awaited()


@pytest.mark.parametrize(
    ("limit", "reason"),
    [(1, "browser_request_limit"), (16, "browser_dom_size_limit")],
)
@pytest.mark.browser
@pytest.mark.skipif(
    os.environ.get("CRAWLER_RUN_BROWSER_TESTS") != "1",
    reason="Explicit browser runtime test",
)
async def test_browser_request_and_dom_limits(limit: int, reason: str) -> None:
    settings = Settings(browser_fallback=True, browser_max_requests=limit, max_bytes=1024)
    fetcher = SafeFetcher(settings)
    fetcher._request = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            RawResponse(404, {}, b""),
            RawResponse(
                200,
                {"content-type": "application/javascript"},
                b"document.body.innerText = 'Orchard notes. '.repeat(500);",
            ),
        ]
    )
    initial = FetchedPage(
        "https://example.com/app",
        b"<html><body><script src='/app.js'></script></body></html>",
        200,
        "text/html",
    )
    with pytest.raises(FetchError) as error:
        await BrowserRenderer(settings, fetcher).render(initial)
    assert error.value.reason == reason
