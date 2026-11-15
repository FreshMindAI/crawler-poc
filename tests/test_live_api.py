import asyncio
import socket
from pathlib import Path

import httpx
import uvicorn

from crawler_poc.api import create_app
from crawler_poc.config import Settings


async def test_real_http_api_starts_and_rejects_forbidden_input(tmp_path: Path) -> None:
    key = "test-only-loopback-api-smoke-key"
    application = create_app(
        Settings(
            api_key=key,
            database_url=f"sqlite:///{tmp_path / 'jobs.db'}",
            content_root=tmp_path / "objects",
        )
    )
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
            base_url=f"http://127.0.0.1:{port}", trust_env=False
        ) as client:
            assert (await client.get("/health/ready")).status_code == 200
            assert (await client.get("/metrics")).status_code == 401
            response = await client.post(
                "/v1/crawls",
                json={"url": "https://example.com/"},
                headers={"X-API-Key": key},
            )
            assert response.status_code == 202
            job = response.json()["job_ids"][0]
            assert (await client.get(f"/v1/crawls/{job}", headers={"X-API-Key": key})).json()[
                "status"
            ] == "queued"
            assert (
                await client.post(
                    "/v1/crawls",
                    json={"url": "http://169.254.169.254/"},
                    headers={"X-API-Key": key},
                )
            ).status_code == 422
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, timeout=5)
        listener.close()
