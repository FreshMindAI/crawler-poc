import asyncio
import gzip
import hashlib
import json
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from crawler_poc.models import normalize_url, url_id

metadata = sa.MetaData()
jobs = sa.Table(
    "crawl_jobs",
    metadata,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("url", sa.Text, nullable=False),
    sa.Column("url_id", sa.String(64), nullable=False, index=True),
    sa.Column("generation", sa.String(80), nullable=False),
    sa.Column("source_run_id", sa.String(80)),
    sa.Column("source_month", sa.String(7)),
    sa.Column("top_k", sa.Integer, nullable=False),
    sa.Column("status", sa.String(20), nullable=False, index=True),
    sa.Column("attempts", sa.Integer, nullable=False, default=0),
    sa.Column("token", sa.Integer, nullable=False, default=0),
    sa.Column("available_at", sa.Float, nullable=False),
    sa.Column("lease_until", sa.Float, nullable=False, default=0),
    sa.Column("created_at", sa.Float, nullable=False),
    sa.Column("updated_at", sa.Float, nullable=False),
    sa.Column("result", sa.Text),
)
documents = sa.Table(
    "documents_latest",
    metadata,
    sa.Column("url_id", sa.String(64), primary_key=True),
    sa.Column("version_at", sa.Float, nullable=False),
    sa.Column("result", sa.Text, nullable=False),
)
idempotency = sa.Table(
    "idempotency_keys",
    metadata,
    sa.Column("id", sa.String(64), primary_key=True),
    sa.Column("payload_hash", sa.String(64), nullable=False),
    sa.Column("response", sa.Text, nullable=False),
)
origins = sa.Table(
    "origin_state",
    metadata,
    sa.Column("origin", sa.String(512), primary_key=True),
    sa.Column("owner", sa.String(64), nullable=False),
    sa.Column("lease_until", sa.Float, nullable=False),
    sa.Column("next_at", sa.Float, nullable=False),
)
outbox = sa.Table(
    "result_outbox",
    metadata,
    sa.Column("event_id", sa.String(64), primary_key=True),
    sa.Column("payload", sa.Text, nullable=False),
    sa.Column("batch_id", sa.String(64), index=True),
    sa.Column("published", sa.Boolean, nullable=False, default=False),
)
publications = sa.Table(
    "publish_batches",
    metadata,
    sa.Column("batch_id", sa.String(64), primary_key=True),
    sa.Column("state", sa.String(20), nullable=False),
    sa.Column("snapshot_id", sa.String(80)),
    sa.Column("row_count", sa.Integer, nullable=False),
)
inputs = sa.Table(
    "input_records",
    metadata,
    sa.Column("run_id", sa.String(80), primary_key=True),
    sa.Column("offset", sa.BigInteger, primary_key=True),
    sa.Column("job_id", sa.String(64)),
    sa.Column("state", sa.String(20), nullable=False),
    sa.Column("source_month", sa.String(7), nullable=False),
)
budgets = sa.Table(
    "api_budgets",
    metadata,
    sa.Column("bucket", sa.BigInteger, primary_key=True),
    sa.Column("requests", sa.Integer, nullable=False),
)
runs = sa.Table(
    "crawl_runs",
    metadata,
    sa.Column("run_id", sa.String(80), primary_key=True),
    sa.Column("fingerprint", sa.String(64), nullable=False),
    sa.Column("source_month", sa.String(7), nullable=False),
    sa.Column("high_water", sa.BigInteger),
)
sa.Index("ix_input_run_job", inputs.c.run_id, inputs.c.job_id)
sa.Index("ix_job_claim", jobs.c.status, jobs.c.available_at, jobs.c.id)
sa.Index("ix_outbox_pending", outbox.c.published, outbox.c.batch_id)


class IdempotencyConflict(Exception):
    pass


class CapacityExceeded(Exception):
    pass


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Store:
    def __init__(self, database_url: str, max_pending: int = 10000) -> None:
        parsed = sa.engine.make_url(database_url)
        if (
            parsed.drivername.startswith("sqlite")
            and parsed.database
            and parsed.database != ":memory:"
        ):
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        options: dict[str, Any] = {"pool_pre_ping": True}
        if parsed.drivername.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False, "timeout": 30}
        self.engine = sa.create_engine(database_url, **options)
        if self.engine.dialect.name not in {"sqlite", "postgresql"}:
            raise ValueError("Only SQLite development and PostgreSQL control stores are supported")
        if self.engine.dialect.name == "sqlite":
            with self.engine.connect() as conn:
                conn.exec_driver_sql("PRAGMA journal_mode=WAL")
                conn.exec_driver_sql("PRAGMA busy_timeout=30000")
        self.max_pending = max_pending
        metadata.create_all(self.engine)

    def _insert(self, table: sa.Table, **values: Any) -> Any:
        factory = sqlite_insert if self.engine.dialect.name == "sqlite" else pg_insert
        return factory(table).values(**values).on_conflict_do_nothing()

    def close(self) -> None:
        self.engine.dispose()

    def submit(
        self,
        urls: list[str],
        generation: str = "initial",
        top_k: int = 5,
        key: str | None = None,
        principal: str = "api",
        source_run_id: str | None = None,
        source_month: str | None = None,
    ) -> list[str]:
        normalized = [normalize_url(value) for value in urls]
        payload_hash = url_id(json_text([normalized, generation, top_k]))
        key_id = url_id(principal + "\0" + key) if key else None
        identifiers = [
            url_id(json_text([principal, value, generation, top_k])) for value in normalized
        ]
        with self.engine.begin() as conn:
            if self.engine.dialect.name == "sqlite":
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                conn.execute(sa.text("SELECT pg_advisory_xact_lock(348192734)"))
            if key_id:
                conn.execute(
                    self._insert(
                        idempotency,
                        id=key_id,
                        payload_hash=payload_hash,
                        response=json_text(identifiers),
                    )
                )
                row = conn.execute(sa.select(idempotency).where(idempotency.c.id == key_id)).one()
                if row.payload_hash != payload_hash:
                    raise IdempotencyConflict
            job_count = (
                sa.select(sa.func.count()).select_from(jobs).where(jobs.c.status != "terminal")
            )
            event_count = sa.select(sa.func.count()).select_from(outbox).where(~outbox.c.published)
            pending = (
                conn.scalar(sa.select(job_count.scalar_subquery() + event_count.scalar_subquery()))
                or 0
            )
            if pending + len(set(identifiers)) > self.max_pending:
                existing = (
                    conn.scalar(
                        sa.select(sa.func.count())
                        .select_from(jobs)
                        .where(jobs.c.id.in_(identifiers))
                    )
                    or 0
                )
                if pending + len(set(identifiers)) - existing > self.max_pending:
                    raise CapacityExceeded
            now = time.time()
            for identifier, value in zip(identifiers, normalized, strict=True):
                conn.execute(
                    self._insert(
                        jobs,
                        id=identifier,
                        url=value,
                        url_id=url_id(value),
                        generation=generation,
                        source_run_id=source_run_id,
                        source_month=source_month,
                        top_k=top_k,
                        status="queued",
                        attempts=0,
                        token=0,
                        available_at=now,
                        lease_until=0,
                        created_at=now,
                        updated_at=now,
                    )
                )
        return identifiers

    def get_job(self, identifier: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(jobs).where(jobs.c.id == identifier)).mappings().first()
        if row is None:
            return None
        result = dict(row)
        result["result"] = json.loads(result["result"]) if result["result"] else None
        return result

    def get_document(self, identifier: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            value = conn.scalar(
                sa.select(documents.c.result).where(documents.c.url_id == identifier)
            )
        return json.loads(value) if value else None

    def claim(self, lease_seconds: float) -> dict[str, Any] | None:
        now = time.time()
        eligible = sa.or_(
            sa.and_(jobs.c.status == "queued", jobs.c.available_at <= now),
            sa.and_(jobs.c.status == "running", jobs.c.lease_until < now),
        )
        with self.engine.begin() as conn:
            query = (
                sa.select(jobs.c.id, jobs.c.token)
                .where(eligible)
                .order_by(jobs.c.available_at, jobs.c.id)
                .limit(1)
            )
            if self.engine.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            candidate = conn.execute(query).first()
            if candidate is None:
                return None
            changed = (
                conn.execute(
                    jobs.update()
                    .where(jobs.c.id == candidate.id, jobs.c.token == candidate.token, eligible)
                    .values(
                        status="running",
                        token=jobs.c.token + 1,
                        attempts=jobs.c.attempts + 1,
                        lease_until=now + lease_seconds,
                        updated_at=now,
                    )
                    .returning(jobs)
                )
                .mappings()
                .first()
            )
            return dict(changed) if changed else None

    def heartbeat(self, identifier: str, token: int, lease_seconds: float) -> bool:
        with self.engine.begin() as conn:
            return bool(
                conn.execute(
                    jobs.update()
                    .where(
                        jobs.c.id == identifier, jobs.c.token == token, jobs.c.status == "running"
                    )
                    .values(lease_until=time.time() + lease_seconds)
                ).rowcount
            )

    def retry(self, identifier: str, token: int, delay: float) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                jobs.update()
                .where(jobs.c.id == identifier, jobs.c.token == token, jobs.c.status == "running")
                .values(status="queued", available_at=time.time() + delay, lease_until=0)
            )

    def finish(self, job: dict[str, Any], result: dict[str, Any]) -> bool:
        result = {
            **result,
            "schema_version": 1,
            "event_id": job["id"],
            "job_id": job["id"],
            "url_id": job["url_id"],
            "normalized_url": job["url"],
            "generation": job["generation"],
            "normalization_version": "conservative-url-v1",
            "fetcher_version": "guarded-aiohttp-v1",
            "observed_at": time.time(),
            "attempt_count": job["attempts"],
            "run_id": job.get("source_run_id"),
            "source_month": job.get("source_month"),
        }
        payload = json_text(result)
        with self.engine.begin() as conn:
            changed = conn.execute(
                jobs.update()
                .where(
                    jobs.c.id == job["id"], jobs.c.token == job["token"], jobs.c.status == "running"
                )
                .values(status="terminal", result=payload, lease_until=0, updated_at=time.time())
            )
            if not changed.rowcount:
                return False
            conn.execute(self._insert(outbox, event_id=job["id"], payload=payload, published=False))
            if result["outcome"] == "success":
                conn.execute(
                    self._insert(
                        documents,
                        url_id=job["url_id"],
                        version_at=job["created_at"],
                        result=payload,
                    )
                )
                conn.execute(
                    documents.update()
                    .where(
                        documents.c.url_id == job["url_id"],
                        documents.c.version_at <= job["created_at"],
                    )
                    .values(version_at=job["created_at"], result=payload)
                )
        return True

    def cancel(self, identifier: str) -> bool:
        with self.engine.begin() as conn:
            changed = conn.execute(
                jobs.update()
                .where(jobs.c.id == identifier, jobs.c.status != "terminal")
                .values(
                    status="terminal",
                    token=jobs.c.token + 1,
                    lease_until=0,
                    result=json_text({"outcome": "canceled", "reason": "caller_canceled"}),
                    updated_at=time.time(),
                )
            )
            return bool(changed.rowcount)

    def counts(self) -> dict[str, int]:
        with self.engine.connect() as conn:
            values = {
                str(state): cast(int, count)
                for state, count in conn.execute(
                    sa.select(jobs.c.status, sa.func.count()).group_by(jobs.c.status)
                )
            }
            values["unpublished"] = (
                conn.scalar(
                    sa.select(sa.func.count()).select_from(outbox).where(~outbox.c.published)
                )
                or 0
            )
            return values

    def ping(self) -> None:
        with self.engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))

    def queue_age(self) -> float:
        with self.engine.connect() as conn:
            oldest = conn.scalar(
                sa.select(sa.func.min(jobs.c.created_at)).where(jobs.c.status != "terminal")
            )
        return max(0, time.time() - oldest) if oldest is not None else 0

    def published_batches(self, run_id: str) -> list[tuple[str, int]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(outbox.c.batch_id, sa.func.count())
                .select_from(outbox.join(jobs, jobs.c.id == outbox.c.event_id))
                .where(
                    jobs.c.source_run_id == run_id,
                    outbox.c.published,
                )
                .group_by(outbox.c.batch_id)
                .limit(1001)
            ).all()
        if len(rows) > 1000:
            raise ValueError("Too many batches for bounded workflow reporting")
        return [(str(batch), cast(int, count)) for batch, count in rows]

    def acquire_origin(self, origin: str, owner: str, ttl: float) -> bool:
        now = time.time()
        with self.engine.begin() as conn:
            conn.execute(self._insert(origins, origin=origin, owner="", lease_until=0, next_at=0))
            return bool(
                conn.execute(
                    origins.update()
                    .where(
                        origins.c.origin == origin,
                        origins.c.lease_until <= now,
                        origins.c.next_at <= now,
                    )
                    .values(owner=owner, lease_until=now + ttl)
                ).rowcount
            )

    def release_origin(self, origin: str, owner: str, delay: float) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                origins.update()
                .where(origins.c.origin == origin, origins.c.owner == owner)
                .values(owner="", lease_until=0, next_at=time.time() + delay)
            )

    def record_inputs(
        self,
        run_id: str,
        month: str,
        records: list[tuple[int, str | None, str]],
    ) -> None:
        with self.engine.begin() as conn:
            for offset, job_id, state in records:
                if job_id:
                    prior = conn.scalar(
                        sa.select(inputs.c.offset)
                        .where(inputs.c.run_id == run_id, inputs.c.job_id == job_id)
                        .limit(1)
                    )
                    state = "duplicate" if prior is not None else "admitted"
                conn.execute(
                    self._insert(
                        inputs,
                        run_id=run_id,
                        offset=offset,
                        job_id=job_id,
                        state=state,
                        source_month=month,
                    )
                )

    def ensure_run(
        self,
        run_id: str,
        fingerprint: str,
        month: str,
        high_water: int | None = None,
    ) -> int | None:
        with self.engine.begin() as conn:
            conn.execute(
                self._insert(
                    runs,
                    run_id=run_id,
                    fingerprint=fingerprint,
                    source_month=month,
                    high_water=high_water,
                )
            )
            row = conn.execute(sa.select(runs).where(runs.c.run_id == run_id)).one()
            if row.fingerprint != fingerprint or row.source_month != month:
                raise ValueError("Run ID already belongs to a different source or month")
            return row.high_water

    def allow_request(self, limit: int) -> bool:
        bucket = int(time.time() // 60)
        with self.engine.begin() as conn:
            conn.execute(self._insert(budgets, bucket=bucket, requests=0))
            count = conn.scalar(
                budgets.update()
                .where(budgets.c.bucket == bucket)
                .values(requests=budgets.c.requests + 1)
                .returning(budgets.c.requests)
            )
            conn.execute(budgets.delete().where(budgets.c.bucket < bucket - 2))
            return bool(count is not None and count <= limit)

    def input_progress(self, run_id: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            last = conn.scalar(
                sa.select(sa.func.max(inputs.c.offset)).where(inputs.c.run_id == run_id)
            )
            counts = {
                str(state): cast(int, count)
                for state, count in conn.execute(
                    sa.select(inputs.c.state, sa.func.count())
                    .where(inputs.c.run_id == run_id)
                    .group_by(inputs.c.state)
                )
            }
        return {"last_offset": last or 0, "counts": counts}

    def prepare_batch(self, limit: int = 1000) -> tuple[str, list[dict[str, Any]]] | None:
        with self.engine.begin() as conn:
            if self.engine.dialect.name == "sqlite":
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                conn.execute(sa.text("SELECT pg_advisory_xact_lock(348192735)"))
            previous = conn.scalar(
                sa.select(publications.c.batch_id)
                .where(publications.c.state == "pending")
                .order_by(publications.c.batch_id)
                .limit(1)
            )
            if previous:
                rows: Any = conn.execute(
                    sa.select(outbox.c.payload).where(outbox.c.batch_id == previous)
                ).scalars()
                return previous, [json.loads(value) for value in rows]
            query = (
                sa.select(outbox.c.event_id)
                .where(outbox.c.batch_id.is_(None), ~outbox.c.published)
                .order_by(outbox.c.event_id)
                .limit(limit)
            )
            if self.engine.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            identifiers: list[str] = list(conn.execute(query).scalars())
            if not identifiers:
                return None
            batch_id = url_id(json_text(identifiers))
            conn.execute(
                self._insert(
                    publications, batch_id=batch_id, state="pending", row_count=len(identifiers)
                )
            )
            conn.execute(
                outbox.update()
                .where(outbox.c.event_id.in_(identifiers), outbox.c.batch_id.is_(None))
                .values(batch_id=batch_id)
            )
            rows = conn.execute(
                sa.select(outbox.c.payload).where(outbox.c.batch_id == batch_id)
            ).scalars()
            return batch_id, [json.loads(value) for value in rows]

    def acknowledge(self, batch_id: str, snapshot_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                publications.update()
                .where(publications.c.batch_id == batch_id)
                .values(state="published", snapshot_id=snapshot_id)
            )
            conn.execute(
                outbox.update().where(outbox.c.batch_id == batch_id).values(published=True)
            )


class DatabaseOriginGate:
    def __init__(self, store: Store, delay: float, ttl: float) -> None:
        self.store, self.delay, self.ttl = store, delay, ttl

    @asynccontextmanager
    async def slot(self, origin: str) -> AsyncIterator[None]:
        owner = uuid.uuid4().hex
        while not await asyncio.to_thread(  # noqa: ASYNC110 - shared DB lease, no local event
            self.store.acquire_origin, origin, owner, self.ttl
        ):
            await asyncio.sleep(0.1)
        try:
            yield
        finally:
            await asyncio.shield(
                asyncio.to_thread(self.store.release_origin, origin, owner, self.delay)
            )


class ContentStore:
    def __init__(self, root: Path | str) -> None:
        self.remote: Any = None
        if str(root).startswith("gs://"):
            from urllib.parse import urlsplit

            from google.cloud.storage import Client

            parsed = urlsplit(str(root))
            if not parsed.netloc:
                raise ValueError("GCS object root requires a bucket")
            self.remote = Client().bucket(parsed.netloc)
            self.prefix = parsed.path.strip("/")
            self.root = Path(".")
        else:
            self.root = Path(root)
            self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        if self.remote is not None:
            from google.api_core.exceptions import PreconditionFailed

            name = "/".join(filter(None, [self.prefix, digest[:2], digest + ".gz"]))
            try:
                self.remote.blob(name).upload_from_string(
                    gzip.compress(data, mtime=0),
                    content_type="application/gzip",
                    if_generation_match=0,
                    timeout=30,
                )
            except PreconditionFailed:
                pass
            return digest
        target = self.root / digest[:2] / (digest + ".gz")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary = target.with_suffix("." + uuid.uuid4().hex + ".tmp")
            try:
                with temporary.open("xb") as stream:
                    stream.write(gzip.compress(data, mtime=0))
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return digest

    def get(self, digest: str) -> bytes:
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("Invalid content reference")
        if self.remote is not None:
            import io

            name = "/".join(filter(None, [self.prefix, digest[:2], digest + ".gz"]))
            compressed = self.remote.blob(name).download_as_bytes(
                start=0, end=20 * 1024 * 1024, timeout=30
            )
            stream: Any = gzip.GzipFile(fileobj=io.BytesIO(compressed))
        else:
            stream = gzip.open(self.root / digest[:2] / (digest + ".gz"), "rb")
        with stream:
            data = stream.read(20 * 1024 * 1024 + 1)
        if len(data) > 20 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Content integrity/size check failed")
        return data
