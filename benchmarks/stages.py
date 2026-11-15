"""Controlled stage workloads: no public websites or cloud resources."""

import argparse
import asyncio
import secrets
import socket
import statistics
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import aiohttp
import httpx
import psutil
import uvicorn
from aiohttp import web
from pydantic import SecretStr

from crawler_poc.api import create_app
from crawler_poc.benchmark import save_report
from crawler_poc.config import Settings
from crawler_poc.lakehouse import IcebergPublisher, local_catalog
from crawler_poc.storage import ContentStore, Store


async def bounded_requests(operation: Any, records: int, samples: list[float]) -> None:
    queue: asyncio.Queue[int | None] = asyncio.Queue(maxsize=32)

    async def produce() -> None:
        for index in range(records):
            await queue.put(index)
        for _ in range(8):
            await queue.put(None)

    async def consume() -> None:
        while (index := await queue.get()) is not None:
            started = time.perf_counter()
            await operation()
            if index % max(1, records // 1000) == 0:
                samples.append(time.perf_counter() - started)

    await asyncio.gather(produce(), *(consume() for _ in range(8)))


async def fetch_stage(records: int, samples: list[float]) -> dict[str, Any]:
    payload = (Path("tests") / "fixtures" / "product.html").read_bytes()

    async def page(_: web.Request) -> web.Response:
        return web.Response(body=payload, content_type="text/html")

    application = web.Application()
    application.router.add_get("/", page)
    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    assert site._server
    port = cast(Any, site._server).sockets[0].getsockname()[1]
    try:
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=8), trust_env=False
        ) as client:

            async def get() -> None:
                async with client.get(f"http://127.0.0.1:{port}/") as response:
                    assert response.status == 200 and await response.read() == payload

            await bounded_requests(get, records, samples)
    finally:
        await runner.cleanup()
    return {"body_bytes": len(payload), "scope": "raw pooled loopback HTTP; not full SafeFetcher"}


def storage_stage(root: Path, records: int) -> dict[str, Any]:
    store = Store(f"sqlite:///{root / 'jobs.db'}", max_pending=records + 1)
    catalog = local_catalog(root / "iceberg")
    try:
        body = ContentStore(root / "objects").put(b"synthetic benchmark content")
        for start in range(0, records, 100):
            store.submit(
                [
                    f"https://example.com/item/{index}"
                    for index in range(start, min(start + 100, records))
                ]
            )
        for _ in range(records):
            job = store.claim(30)
            assert job and store.finish(
                job,
                {
                    "outcome": "success",
                    "title": "Synthetic benchmark",
                    "body_ref": body,
                    "topics": [],
                    "body_preview": "synthetic benchmark content",
                },
            )
        publisher = IcebergPublisher(catalog, "crawler.crawl_events")
        batches = 0
        while publisher.publish(store, 1000)["published"]:
            batches += 1
        assert publisher.table().scan().count() == records
        assert store.counts() == {"terminal": records, "unpublished": 0}
        return {
            "batches": batches,
            "iceberg_rows": records,
            "scope": "SQLite jobs/outbox + real local Iceberg; no extraction/HTTP",
        }
    finally:
        store.close()
        catalog.engine.dispose()


async def api_stage(root: Path, records: int, samples: list[float]) -> dict[str, Any]:
    key = secrets.token_urlsafe(32)
    settings = Settings(
        database_url=f"sqlite:///{root / 'jobs.db'}",
        api_key=SecretStr(key),
        object_uri=None,
        content_root=root / "objects",
        api_requests_per_minute=10000,
    )
    store = Store(settings.database_url)
    store.submit(["https://example.com/fixture"])
    job = store.claim(30)
    assert job and store.finish(job, {"outcome": "success", "title": "Warm metadata fixture"})
    application = create_app(settings, store)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(application, log_level="error", access_log=False))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.01)
        assert server.started and not serving.done()
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}",
            trust_env=False,
            limits=httpx.Limits(max_connections=8),
            timeout=10,
        ) as client:
            assert (await client.get("/health/ready")).status_code == 200

            async def get() -> None:
                response = await client.get(
                    f"/v1/documents/{job['url_id']}", headers={"X-API-Key": key}
                )
                assert response.status_code == 200
                assert response.json()["title"] == "Warm metadata fixture"

            await bounded_requests(get, records, samples)
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, timeout=5)
        listener.close()
        store.close()
    return {"scope": "authenticated real loopback TCP API, warm single key, eight clients"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["fetch", "storage", "api"])
    parser.add_argument("--records", type=int, default=10000)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not 1 <= args.records <= 10000:
        parser.error("Stage workloads are bounded to 10000 records")
    process = psutil.Process()
    samples: list[float] = []
    rss = [process.memory_info().rss]
    started, cpu_started = time.perf_counter(), time.process_time()
    with TemporaryDirectory(prefix="crawler-stage-") as directory:
        root = Path(directory)
        if args.mode == "storage":
            details = storage_stage(root, args.records)
        elif args.mode == "api":
            details = asyncio.run(api_stage(root, args.records, samples))
        else:
            details = asyncio.run(fetch_stage(args.records, samples))
        rss.append(process.memory_info().rss)
    elapsed = time.perf_counter() - started
    ordered = sorted(samples)
    report = {
        "mode": args.mode,
        "records": args.records,
        "seconds": elapsed,
        "records_per_second": args.records / elapsed,
        "cpu_seconds": time.process_time() - cpu_started,
        "rss_before_after_max_bytes": max(rss),
        "errors": 0,
        "external_network_requests": 0,
        "concurrency": 8 if args.mode != "storage" else 1,
        "sample_latency_p50_ms": statistics.median(samples) * 1000 if samples else None,
        "sample_latency_p95_ms": (
            ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] * 1000 if samples else None
        ),
        "limitations": "Single synthetic run; shared CPU; RSS before/after only, not peak.",
        **details,
    }
    save_report(report, args.output)


if __name__ == "__main__":
    main()
