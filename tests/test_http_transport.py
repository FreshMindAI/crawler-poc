import asyncio
import gzip
import socket
from collections.abc import AsyncIterator
from typing import Any

import aiohttp
import pytest
from aiohttp import web
from aiohttp.abc import AbstractResolver

from crawler_poc.config import Settings
from crawler_poc.fetching import FetchError, SafeFetcher
from crawler_poc.models import Outcome


class FixtureResolver(AbstractResolver):
    """Test-only transport wiring; production still rejects all private addresses."""

    def __init__(self, port: int) -> None:
        self.port = port

    async def resolve(self, host: str, port: int = 0, family: int = 0) -> list[Any]:
        return [
            {
                "hostname": host,
                "host": "127.0.0.1",
                "port": self.port,
                "family": socket.AF_INET,
                "proto": 0,
                "flags": 0,
            }
        ]

    async def close(self) -> None:
        pass


@pytest.fixture
async def transport() -> AsyncIterator[SafeFetcher]:
    async def handler(request: web.Request) -> web.Response:
        if request.path == "/robots.txt":
            return web.Response(status=404)
        if request.path == "/slow":
            await asyncio.sleep(0.2)
        if request.path == "/binary":
            return web.Response(body=b"image", content_type="image/png")
        if request.path == "/wire":
            return web.Response(body=b"x" * 2048, content_type="text/html")
        payload = b"<html><title>Fixture</title><body>Bounded fixture</body></html>"
        if request.path in {"/bomb", "/unavailable"}:
            payload = b"A" * 10000
        if request.path == "/large":
            payload = b"<html><body>" + b"A" * (6 * 1024 * 1024) + b"</body></html>"
        body = gzip.compress(payload)
        if request.path == "/trailing":
            body += gzip.compress(b"hidden second member")
        return web.Response(
            body=body,
            status=503 if request.path == "/unavailable" else 200,
            content_type="text/html",
            headers={"Content-Encoding": "gzip"},
        )

    application = web.Application()
    application.router.add_get("/{path:.*}", handler)
    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    assert site._server
    port = site._server.sockets[0].getsockname()[1]
    fetcher = SafeFetcher(Settings(max_bytes=1024, origin_delay=0.1, request_timeout=2))
    connector = aiohttp.TCPConnector(resolver=FixtureResolver(port))
    async with aiohttp.ClientSession(connector=connector, auto_decompress=False) as session:
        fetcher.session = session
        yield fetcher
    await runner.cleanup()


async def test_real_socket_gzip_decode(transport: SafeFetcher) -> None:
    page = await transport.fetch("http://fixture.example/page")
    assert b"<title>Fixture</title>" in page.body


async def test_default_budget_accepts_large_bounded_gzip_html(transport: SafeFetcher) -> None:
    transport.settings.max_bytes = Settings().max_bytes
    page = await transport.fetch("http://fixture.example/large")
    assert len(page.body) > 5 * 1024 * 1024
    assert page.body.endswith(b"</body></html>")


async def test_wire_budget_still_applies_with_larger_decoded_budget(
    transport: SafeFetcher,
) -> None:
    transport.settings.max_bytes = 16384
    transport.settings.max_wire_bytes = 1024
    with pytest.raises(FetchError) as error:
        await transport.fetch("http://fixture.example/wire")
    assert error.value.reason == "wire_size_limit"
    assert error.value.http_status == 200
    assert error.value.limit_bytes == 1024
    assert error.value.observed_bytes > error.value.limit_bytes


async def test_http_failure_is_not_masked_by_oversized_error_body(
    transport: SafeFetcher,
) -> None:
    with pytest.raises(FetchError) as error:
        await transport.fetch("http://fixture.example/unavailable")
    assert error.value.reason == "transient_http_status"
    assert error.value.http_status == 503
    assert error.value.retryable


@pytest.mark.parametrize(
    ("path", "outcome"),
    [
        ("bomb", Outcome.TOO_LARGE),
        ("binary", Outcome.UNSUPPORTED),
        ("trailing", Outcome.UNSUPPORTED),
    ],
)
async def test_real_socket_enforces_limits(
    transport: SafeFetcher,
    path: str,
    outcome: Outcome,
) -> None:
    with pytest.raises(FetchError) as error:
        await transport.fetch(f"http://fixture.example/{path}")
    assert error.value.outcome == outcome
    if path == "bomb":
        assert error.value.reason == "decoded_size_limit"
        assert error.value.limit_bytes == 1024
        assert error.value.observed_bytes == 1025
        assert error.value.http_status == 200


async def test_real_socket_times_out(transport: SafeFetcher) -> None:
    transport.settings.request_timeout = 0.05
    # Seed robots so the deliberately tiny budget tests the page rather than host pacing.
    await transport._robots_allowed("http://fixture.example/slow")
    transport.gate.next_at.clear()
    with pytest.raises(FetchError) as error:
        await transport.fetch("http://fixture.example/slow")
    assert error.value.retryable


async def test_guarded_dns_makes_zero_forbidden_socket_requests() -> None:
    from unittest.mock import AsyncMock

    from crawler_poc.fetching import GuardedResolver

    requests = 0

    async def forbidden(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal requests
        requests += 1
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(forbidden, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    delegate = AsyncMock()
    delegate.resolve.return_value = [
        {
            "hostname": "forbidden.fixture",
            "host": "127.0.0.1",
            "port": port,
            "family": socket.AF_INET,
            "proto": 0,
            "flags": 0,
        }
    ]
    fetcher = SafeFetcher(Settings())
    try:
        connector = aiohttp.TCPConnector(resolver=GuardedResolver(delegate))
        async with aiohttp.ClientSession(connector=connector) as session:
            fetcher.session = session
            with pytest.raises(FetchError) as error:
                await fetcher.fetch("http://forbidden.fixture/")
            assert error.value.outcome == Outcome.POLICY_BLOCKED
        assert requests == 0
    finally:
        server.close()
        await server.wait_closed()
