import asyncio
import json
import os
import socket
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
import uvicorn

from crawler_poc.api import create_app
from crawler_poc.config import Settings
from crawler_poc.fetching import FetchedPage
from crawler_poc.storage import ContentStore, Store
from crawler_poc.worker import Worker

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("CRAWLER_RUN_BROWSER_TESTS") != "1",
        reason="Explicit installed-browser UI test",
    ),
]
KEY = "fixture-only-ui-browser-key-12345678"


@pytest_asyncio.fixture
async def workspace(tmp_path: Path):
    from playwright.async_api import async_playwright

    settings = Settings(
        api_key=KEY,
        database_url=f"sqlite:///{tmp_path / 'jobs.db'}",
        content_root=tmp_path / "objects",
        api_requests_per_minute=1000,
    )
    store = Store(settings.database_url)
    application = create_app(settings, store)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(application, log_level="error", access_log=False))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.02)
        assert server.started and not serving.done()
        async with async_playwright() as runtime:
            browser = await runtime.chromium.launch(channel="msedge", headless=True)
            try:
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(f"http://127.0.0.1:{listener.getsockname()[1]}/")
                yield page, context, store, settings
            finally:
                await browser.close()
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, timeout=5)
        listener.close()
        store.close()


async def submit(page, key: str = KEY) -> None:
    await page.get_by_label("API key", exact=True).fill(key)
    await page.get_by_label("Page URL", exact=True).fill("https://example.com/article")
    await page.get_by_role("button", name="Inspect page").click()


async def test_real_ui_api_worker_content_and_responsive_layout(workspace, tmp_path: Path) -> None:
    from playwright.async_api import expect

    page, context, store, settings = workspace
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    await page.keyboard.press("Tab")
    await expect(page.get_by_role("link", name="Skip to workspace")).to_be_focused()
    await page.get_by_label("API key", exact=True).fill(KEY)
    await page.get_by_label("Page URL", exact=True).fill("https://example.com/article")
    await page.get_by_label("Page URL", exact=True).press("Enter")
    await expect(page.get_by_role("heading", name="Waiting for a worker")).to_be_visible()
    transport = AsyncMock()
    source = (Path(__file__).parent / "fixtures" / "product.html").read_bytes()
    transport.fetch.return_value = FetchedPage(
        "https://example.com/article", source, 200, "text/html"
    )
    worker = Worker(settings, store, ContentStore(settings.content_root), transport)
    assert await worker.once()
    await expect(page.get_by_role("heading", name="Extraction complete")).to_be_visible(
        timeout=10000
    )
    await expect(page.locator("#result-title")).not_to_be_empty()
    await page.get_by_role("button", name="Load readable text").click()
    await expect(page.locator("#body-text")).to_contain_text("toaster")
    await page.get_by_text("Inspect response JSON", exact=True).click()
    await expect(page.locator("#json-output")).to_contain_text('"outcome": "success"')
    async with page.expect_download() as downloaded:
        await page.get_by_role("button", name="Download JSON").click()
    download = await downloaded.value
    path = await download.path()
    assert path is not None
    assert KEY not in await asyncio.to_thread(Path(path).read_text)
    assert (
        await page.evaluate("Object.keys(localStorage).length + Object.keys(sessionStorage).length")
        == 0
    )
    assert not await context.cookies()
    await page.screenshot(path=str(tmp_path / "desktop.png"), full_page=True)
    await page.set_viewport_size({"width": 390, "height": 844})
    assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    await page.screenshot(path=str(tmp_path / "mobile.png"), full_page=True)
    print(f"UI screenshots: {tmp_path}")
    await page.get_by_role("button", name="Clear workspace & key").click()
    await expect(page.get_by_label("API key", exact=True)).to_have_value("")
    await expect(page.locator("#results")).to_be_hidden()
    assert not errors


async def test_auth_failure_and_job_cancellation(workspace) -> None:
    from playwright.async_api import expect

    page, _, _, _ = workspace
    await submit(page, "wrong-key")
    await expect(page.get_by_role("alert")).to_contain_text("API key not accepted")
    await expect(page.get_by_role("button", name="Inspect page")).to_be_enabled()
    await submit(page)
    await expect(page.get_by_role("heading", name="Waiting for a worker")).to_be_visible()
    await page.get_by_role("button", name="Cancel crawl", exact=True).click()
    await expect(page.get_by_role("heading", name="Crawl canceled")).to_be_visible()
    await expect(page.locator("#results")).to_be_hidden()


async def test_failed_result_does_not_render_challenge_content(workspace) -> None:
    from playwright.async_api import expect

    page, _, store, _ = workspace
    await submit(page)
    await expect(page.get_by_role("heading", name="Waiting for a worker")).to_be_visible()
    store.finish(
        store.claim(120),
        {
            "outcome": "target_blocked",
            "reason": "target_access_denied",
            "http_status": 403,
            "metadata": {"failure_stage": "fetch"},
        },
    )
    await expect(page.get_by_role("heading", name="No extraction returned")).to_be_visible(
        timeout=10000
    )
    await expect(page.get_by_role("alert")).to_contain_text("HTTP 403")
    await expect(page.locator("#results")).to_be_hidden()


async def test_extracted_html_is_only_text_and_unicode_pagination_is_exact(workspace) -> None:
    from playwright.async_api import expect

    page, _, store, settings = workspace
    await submit(page)
    await expect(page.get_by_role("heading", name="Waiting for a worker")).to_be_visible()
    malicious = "<img src=x onerror=alert('xss')>"
    body = "\U0001f333" * 16000 + "<script>unsafe()</script>"
    store.finish(
        store.claim(120),
        {
            "outcome": "success",
            "title": malicious,
            "description": malicious,
            "body_ref": ContentStore(settings.content_root).put(body.encode()),
            "body_preview": malicious,
            "body_characters": len(body),
            "topics": [{"phrase": malicious, "raw_score": 0.1}],
        },
    )
    await expect(page.get_by_role("heading", name="Extraction complete")).to_be_visible(
        timeout=10000
    )
    await expect(page.locator("#result-title")).to_have_text(malicious)
    assert await page.locator("#results img, #results script").count() == 0
    await page.get_by_role("button", name="Load readable text").click()
    await expect(page.get_by_role("button", name="Load more text")).to_be_visible()
    await page.get_by_role("button", name="Load more text").click()
    await expect(page.locator("#body-text")).to_have_text(body)
    assert await page.locator("#body-text script").count() == 0


async def test_poll_rate_limit_pauses_and_can_resume(workspace) -> None:
    from playwright.async_api import expect

    page, _, _, _ = workspace

    async def limited(route):
        if route.request.method == "GET":
            await route.fulfill(status=429, json={"detail": "Request budget exhausted"})
        else:
            await route.continue_()

    await page.route("**/v1/crawls/*", limited)
    await submit(page)
    await expect(page.get_by_role("alert")).to_contain_text("60 seconds")
    await expect(page.get_by_role("button", name="Resume monitoring")).to_be_visible()
    await page.unroute("**/v1/crawls/*", limited)
    await page.get_by_role("button", name="Resume monitoring").click()
    await expect(page.get_by_role("heading", name="Waiting for a worker")).to_be_visible()


async def test_clearing_during_a_poll_ignores_the_late_result(workspace) -> None:
    from playwright.async_api import expect

    page, _, _, _ = workspace
    requested = asyncio.Event()
    release = asyncio.Event()
    delivered = asyncio.Event()

    async def delayed(route):
        requested.set()
        await release.wait()
        await route.fulfill(
            json={
                "status": "terminal",
                "result": {"outcome": "success", "title": "Stale result"},
            },
        )
        delivered.set()

    await page.route("**/v1/crawls/*", delayed)
    try:
        await submit(page)
        await asyncio.wait_for(requested.wait(), timeout=5)
        await page.get_by_role("button", name="Clear workspace & key").click()
        release.set()
        await asyncio.wait_for(delivered.wait(), timeout=5)
        await page.wait_for_load_state("networkidle")
        await expect(page.get_by_label("API key", exact=True)).to_have_value("")
        await expect(page.locator("#results")).to_be_hidden()
        await expect(page.locator("#progress")).to_be_hidden()
        await expect(page.get_by_role("heading", name="A page, made readable.")).to_be_visible()
    finally:
        release.set()


async def test_batch_results_preserve_urls_outcomes_and_exact_bodies(workspace, tmp_path) -> None:
    from playwright.async_api import expect

    page, _, store, settings = workspace
    urls = [
        "https://example.com/product?a=1,2",
        "https://example.com/blocked",
        "https://example.com/article",
    ]
    await page.get_by_label("Input mode").select_option("multiple")
    await page.get_by_label("API key", exact=True).fill(KEY)
    await page.get_by_label("Page URLs", exact=True).fill(
        f"  {urls[0]}\n\n{urls[1]}\t{urls[2]}\n{urls[0]}  "
    )
    async with page.expect_response("**/v1/crawls") as accepted:
        await page.get_by_role("button", name="Inspect pages").click()
    response = await accepted.value
    assert response.status == 202
    assert response.request.post_data_json["urls"] == urls + [urls[0]]
    await expect(page.locator("#batch-list button")).to_have_count(3)
    objects = ContentStore(settings.content_root)
    for _ in range(3):
        job = store.claim(120)
        if job["url"] == urls[1]:
            result = {"outcome": "target_blocked", "http_status": 403, "reason": "denied"}
        else:
            text = f"Readable text for {job['url']}"
            result = {
                "outcome": "success",
                "title": job["url"],
                "body_ref": objects.put(text.encode()),
                "body_characters": len(text),
            }
        assert store.finish(job, result)
    await expect(page.locator("#batch-summary")).to_contain_text("3 of 3 finished", timeout=15000)
    for url in (urls[0], urls[2]):
        await page.get_by_role("button", name=f"View {url}", exact=True).click()
        await page.get_by_role("button", name="Load readable text").click()
        await expect(page.locator("#body-text")).to_have_text(f"Readable text for {url}")
    requested = asyncio.Event()
    release = asyncio.Event()
    delivered = asyncio.Event()

    async def delayed_body(route):
        requested.set()
        await release.wait()
        await route.fulfill(body="Wrong body from the previous selection")
        delivered.set()

    await page.route("**/v1/crawls/*/content?**", delayed_body)
    try:
        await page.get_by_role("button", name=f"View {urls[0]}", exact=True).click()
        await page.get_by_role("button", name="Load readable text").click()
        await asyncio.wait_for(requested.wait(), timeout=5)
        await page.get_by_role("button", name=f"View {urls[2]}", exact=True).click()
        release.set()
        await asyncio.wait_for(delivered.wait(), timeout=5)
        await page.wait_for_load_state("networkidle")
        await expect(page.locator("#body-text")).not_to_contain_text("Wrong body")
    finally:
        release.set()
        await page.unroute("**/v1/crawls/*/content?**", delayed_body)
    await page.get_by_role("button", name=f"View {urls[1]}", exact=True).click()
    await expect(page.get_by_role("alert")).to_contain_text("HTTP 403")
    await expect(page.locator("#results")).to_be_hidden()
    async with page.expect_download() as downloaded:
        await page.get_by_role("button", name="Download batch JSON").click()
    path = await (await downloaded.value).path()
    data = json.loads(await asyncio.to_thread(Path(path).read_text))
    assert {job["url"] for job in data} == set(urls)
    assert sum(job["result"]["outcome"] == "success" for job in data) == 2
    assert KEY not in json.dumps(data)
    await page.set_viewport_size({"width": 390, "height": 844})
    assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    await page.screenshot(path=str(tmp_path / "batch-mobile.png"), full_page=True)
    print(f"Batch screenshot: {tmp_path}")


async def test_batch_cancel_only_affects_the_selected_job(workspace) -> None:
    from playwright.async_api import expect

    page, _, store, _ = workspace
    await page.get_by_label("Input mode").select_option("multiple")
    await page.get_by_label("API key", exact=True).fill(KEY)
    await page.get_by_label("Page URLs", exact=True).fill(
        "https://example.com/one\nhttps://example.com/two"
    )
    await page.get_by_role("button", name="Inspect pages").click()
    await page.get_by_role("button", name="View https://example.com/two", exact=True).click()
    await page.get_by_role("button", name="Cancel crawl", exact=True).click()
    await expect(page.get_by_role("heading", name="Crawl canceled")).to_be_visible()
    assert store.counts()["queued"] == 1
    assert store.counts()["terminal"] == 1
    await page.get_by_role("button", name="View https://example.com/one", exact=True).click()
    await expect(page.get_by_role("heading", name="Waiting for a worker")).to_be_visible()
    await expect(page.get_by_role("button", name="Cancel crawl", exact=True)).to_be_visible()


async def test_batch_validation_and_switching_back_to_single(workspace) -> None:
    from playwright.async_api import expect

    page, _, store, _ = workspace
    await page.get_by_label("Input mode").select_option("multiple")
    await page.get_by_label("API key", exact=True).fill(KEY)
    for value, error in [
        ("\n".join(f"https://example.com/{i}" for i in range(101)), "100"),
        ("https://example.com/valid\nftp://example.com/invalid", "HTTP or HTTPS"),
        ("https://example.com/" + "\U0001f333" * 17000, "64 KiB"),
    ]:
        await page.get_by_label("Page URLs", exact=True).fill(value)
        await page.get_by_role("button", name="Inspect pages").click()
        await expect(page.get_by_role("alert")).to_contain_text(error)
        assert store.counts().get("queued", 0) == 0
    await page.get_by_label("Input mode").select_option("single")
    await expect(page.get_by_label("Page URLs", exact=True)).to_be_hidden()
    await submit(page)
    await expect(page.get_by_role("heading", name="Waiting for a worker")).to_be_visible()
    assert store.counts()["queued"] == 1
