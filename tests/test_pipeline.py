from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from crawler_poc.config import Settings
from crawler_poc.fetching import FetchedPage, FetchError
from crawler_poc.models import Outcome
from crawler_poc.pipeline import CrawlPipeline

PRODUCT = (Path(__file__).parent / "fixtures" / "product.html").read_bytes()
SHELL = b"<html><body><div id='app'></div><script src='/app.js'></script></body></html>"


async def test_browser_only_runs_for_successful_js_shell() -> None:
    transport = AsyncMock()
    transport.fetch.return_value = FetchedPage("https://example.com/", SHELL, 200, "text/html")
    pipeline = CrawlPipeline(Settings(browser_fallback=True), transport)
    pipeline.renderer = AsyncMock()
    pipeline.renderer.render.return_value = (
        FetchedPage("https://example.com/", PRODUCT, 200, "text/html", "headless"),
        {"raw_representation": "rendered-dom"},
    )
    result = await pipeline.analyze("https://example.com/")
    assert result.page.page_type == "product"
    assert result.fetched.fetch_method == "headless"
    assert result.initial_body == SHELL
    assert result.page.metadata["fetch_method"] == "headless"
    assert result.timings_ms["total"] >= result.timings_ms["fetch"]
    pipeline.renderer.render.assert_awaited_once()


@pytest.mark.parametrize(
    "source",
    [
        PRODUCT,
        b"<html><head><title>Robot Check</title></head><body><script>run()</script></body></html>",
        b"<html><body><form action='/captcha'><input id='captcha'></form>"
        b"<script>run()</script></body></html>",
    ],
)
async def test_real_content_and_challenges_never_escalate(source: bytes) -> None:
    transport = AsyncMock()
    transport.fetch.return_value = FetchedPage("https://example.com/", source, 200, "text/html")
    pipeline = CrawlPipeline(Settings(browser_fallback=True), transport)
    pipeline.renderer = AsyncMock()
    if source == PRODUCT:
        assert (await pipeline.analyze("https://example.com/")).fetched.fetch_method == "http"
    else:
        with pytest.raises(FetchError) as error:
            await pipeline.analyze("https://example.com/")
        assert error.value.outcome == Outcome.TARGET_BLOCKED
        assert error.value.http_status == 200
    pipeline.renderer.render.assert_not_awaited()


@pytest.mark.parametrize("status", [404, 429])
async def test_non_fallback_http_errors_never_escalate_to_browser(status: int) -> None:
    transport = AsyncMock()
    transport.fetch.side_effect = FetchError(
        Outcome.RETRY_EXHAUSTED, "upstream_status", http_status=status, stage="fetch"
    )
    pipeline = CrawlPipeline(Settings(browser_fallback=True), transport)
    pipeline.renderer = AsyncMock()
    with pytest.raises(FetchError) as error:
        await pipeline.analyze("https://example.com/")
    assert error.value.http_status == status
    pipeline.renderer.fetch_page.assert_not_awaited()


@pytest.mark.parametrize("status", [403, 503])
async def test_blocked_http_403_503_escalates_to_browser_when_enabled(status: int) -> None:
    transport = AsyncMock()
    transport.fetch.side_effect = FetchError(
        Outcome.TARGET_BLOCKED if status == 403 else Outcome.RETRY_EXHAUSTED,
        "upstream_status",
        http_status=status,
        url="https://example.com/item",
        stage="fetch",
    )
    pipeline = CrawlPipeline(Settings(browser_fallback=True), transport)
    pipeline.renderer = AsyncMock()
    pipeline.renderer.fetch_page.return_value = (
        FetchedPage("https://example.com/item", PRODUCT, 200, "text/html", "headless"),
        {"raw_representation": "rendered-dom"},
    )
    result = await pipeline.analyze("https://example.com/item")
    assert result.fetched.fetch_method == "headless"
    assert result.page.page_type == "product"
    pipeline.renderer.fetch_page.assert_awaited_once_with("https://example.com/item")


async def test_disabled_browser_reports_js_limitation() -> None:
    transport = AsyncMock()
    transport.fetch.return_value = FetchedPage("https://example.com/", SHELL, 200, "text/html")
    with pytest.raises(FetchError, match="javascript_only"):
        await CrawlPipeline(Settings(), transport).analyze("https://example.com/")


async def test_render_failure_retains_resource_and_initial_page_evidence() -> None:
    transport = AsyncMock()
    transport.fetch.return_value = FetchedPage(
        "https://example.com/",
        SHELL.replace(b"<body>", b"<head><title>Field app</title></head><body>"),
        200,
        "text/html",
    )
    pipeline = CrawlPipeline(Settings(browser_fallback=True), transport)
    pipeline.renderer = AsyncMock()
    pipeline.renderer.render.side_effect = FetchError(
        Outcome.ROBOTS_DISALLOWED,
        "robots_access_denied",
        stage="robots",
        url="https://cdn.example/robots.txt",
        http_status=403,
    )
    with pytest.raises(FetchError) as error:
        await pipeline.analyze("https://example.com/")
    result = error.value.as_result()
    assert result["http_status"] == 403
    assert result["final_url"] is None
    assert result["metadata"]["initial_http_status"] == "200"
    assert result["metadata"]["partial_title"] == "Field app"
