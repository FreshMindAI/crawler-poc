import asyncio
import contextlib
import hmac
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from crawler_poc.config import Settings
from crawler_poc.models import CrawlRequest
from crawler_poc.storage import CapacityExceeded, ContentStore, IdempotencyConflict, Store


class BodyLimit:
    def __init__(self, app: ASGIApp, limit: int = 65536) -> None:
        self.app, self.limit = app, limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return
        parts: list[bytes] = []
        size = 0
        try:
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    part = message.get("body", b"")
                    size += len(part)
                    if size > self.limit:
                        await PlainTextResponse("Request body exceeds 64 KiB", status_code=413)(
                            scope, receive, send
                        )
                        return
                    parts.append(part)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await PlainTextResponse("Request body timeout", status_code=408)(scope, receive, send)
            return
        sent = False

        async def replay() -> Any:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": b"".join(parts), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def create_app(settings: Settings | None = None, store: Store | None = None) -> FastAPI:
    config = settings or Settings()
    expected = config.api_key.get_secret_value()
    if config.auth_mode == "api_key" and len(expected) < 24:
        raise ValueError(
            "Set CRAWLER_API_KEY to a randomly generated value of at least 24 characters"
        )
    database = store or Store(config.database_url, config.max_pending_jobs)
    content = ContentStore(config.object_uri or config.content_root)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        worker_task: asyncio.Task[None] | None = None
        if config.embedded_worker:
            from crawler_poc.cli import run_workers

            worker_task = asyncio.create_task(run_workers(config, database, drain=False))
        try:
            yield
        finally:
            if worker_task is not None:
                worker_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await worker_task
            if store is None:
                database.close()

    app = FastAPI(title="Crawler POC", version="0.1.0", lifespan=lifespan)
    app.add_middleware(BodyLimit)
    app.state.store = database
    ui_root = Path(__file__).parent / "ui"
    app.mount("/ui", StaticFiles(directory=ui_root), name="ui")

    @app.get("/", include_in_schema=False)
    async def workspace() -> FileResponse:
        return FileResponse(ui_root / "index.html", media_type="text/html")

    @app.get("/v1/config")
    async def client_config() -> dict[str, str]:
        return {"auth_mode": config.auth_mode}

    async def authorize(x_api_key: str = Header(default="")) -> None:
        if config.auth_mode == "api_key" and not hmac.compare_digest(
            x_api_key.encode(), expected.encode()
        ):
            raise HTTPException(401, "Invalid API key")
        if not await asyncio.to_thread(database.allow_request, config.api_requests_per_minute):
            raise HTTPException(429, "Request budget exhausted", headers={"Retry-After": "60"})

    protected = [Depends(authorize)]

    @app.middleware("http")
    async def response_headers(request: Request, call_next: Any) -> Any:
        correlation = uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        if request.url.path == "/" or request.url.path.startswith("/ui/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
            )
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        try:
            await asyncio.to_thread(database.ping)
        except Exception as exc:
            raise HTTPException(503, "Database not ready") from exc
        return {"status": "ready"}

    @app.post("/v1/crawls", status_code=202, dependencies=protected)
    async def submit(
        body: CrawlRequest,
        idempotency_key: str | None = Header(default=None, max_length=128),
    ) -> dict[str, Any]:
        try:
            identifiers = await asyncio.to_thread(
                database.submit, body.urls or [], body.generation, body.top_k, idempotency_key
            )
        except IdempotencyConflict as exc:
            raise HTTPException(409, "Idempotency key already has a different payload") from exc
        except CapacityExceeded as exc:
            raise HTTPException(429, "Pending job capacity reached") from exc
        return {"job_ids": identifiers, "status": "accepted"}

    @app.get("/v1/crawls", dependencies=protected)
    async def list_jobs(
        ids: str = Query(default="", max_length=8000),
    ) -> dict[str, list[dict[str, Any]]]:
        identifiers = [item.strip() for item in ids.split(",") if item.strip()][:100]
        values = await asyncio.to_thread(database.get_jobs, identifiers)
        keys = (
            "id",
            "url_id",
            "url",
            "status",
            "attempts",
            "created_at",
            "updated_at",
            "result",
        )
        return {"jobs": [{key: item[key] for key in keys} for item in values]}

    @app.get("/v1/crawls/{job_id}", dependencies=protected)
    async def job(job_id: str) -> dict[str, Any]:
        value = await asyncio.to_thread(database.get_job, job_id)
        if value is None:
            raise HTTPException(404, "Job not found")
        return {
            key: value[key]
            for key in (
                "id",
                "url_id",
                "url",
                "status",
                "attempts",
                "created_at",
                "updated_at",
                "result",
            )
        }

    @app.post("/v1/crawls/{job_id}/cancel", dependencies=protected)
    async def cancel(job_id: str) -> dict[str, bool]:
        if await asyncio.to_thread(database.get_job, job_id) is None:
            raise HTTPException(404, "Job not found")
        return {"canceled": await asyncio.to_thread(database.cancel, job_id)}

    @app.get("/v1/crawls/{job_id}/content", dependencies=protected)
    async def job_body(
        job_id: str,
        offset: int = Query(default=0, ge=0, le=250000),
        limit: int = Query(default=16000, ge=1, le=64000),
    ) -> PlainTextResponse:
        value = await asyncio.to_thread(database.get_job, job_id)
        if value is None:
            raise HTTPException(404, "Job not found")
        result = value.get("result") or {}
        if result.get("outcome") != "success" or not result.get("body_ref"):
            raise HTTPException(404, "Successful job content not found")
        text = (await asyncio.to_thread(content.get, result["body_ref"])).decode("utf-8")
        return PlainTextResponse(text[offset : offset + limit])

    @app.get("/v1/documents/{identifier}", dependencies=protected)
    async def document(identifier: str) -> dict[str, Any]:
        value = await asyncio.to_thread(database.get_document, identifier)
        if value is None:
            raise HTTPException(404, "Document not found")
        return value

    @app.get("/v1/documents/{identifier}/content", dependencies=protected)
    async def body(
        identifier: str,
        offset: int = Query(default=0, ge=0, le=250000),
        limit: int = Query(default=16000, ge=1, le=64000),
    ) -> PlainTextResponse:
        value = await document(identifier)
        if not value.get("body_ref"):
            raise HTTPException(404, "Content not found")
        text = (await asyncio.to_thread(content.get, value["body_ref"])).decode("utf-8")
        return PlainTextResponse(text[offset : offset + limit])

    @app.get("/metrics", dependencies=protected, response_class=PlainTextResponse)
    async def metrics() -> str:
        values = await asyncio.to_thread(database.counts)
        lines = [f'crawler_jobs{{state="{key}"}} {value}' for key, value in values.items()]
        lines.append(f"crawler_queue_oldest_seconds {await asyncio.to_thread(database.queue_age)}")
        return "\n".join(lines) + "\n"

    return app
