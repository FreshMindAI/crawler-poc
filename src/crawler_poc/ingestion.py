import hashlib
import re
from collections.abc import Iterable, Iterator
from datetime import date
from pathlib import Path
from typing import Any, BinaryIO, cast

import sqlalchemy as sa

from crawler_poc.models import normalize_url, url_id
from crawler_poc.storage import Store


def month_bounds(month: str) -> tuple[date, date]:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError("Month must be YYYY-MM")
    first = date.fromisoformat(month + "-01")
    following = (
        date(first.year + 1, 1, 1) if first.month == 12 else date(first.year, first.month + 1, 1)
    )
    return first, following


def bounded_lines(path: Path) -> Iterator[tuple[int, str]]:
    with path.open("rb") as stream:
        yield from bounded_stream(stream)


def bounded_stream(stream: BinaryIO) -> Iterator[tuple[int, str]]:
    offset = 0
    while True:
        source = stream.readline(8194)
        if not source:
            return
        offset += 1
        oversized = len(source) > 8193
        if not source.endswith(b"\n") and len(source) >= 8194:
            while True:
                remainder = stream.readline(8194)
                if not remainder or remainder.endswith(b"\n"):
                    break
            oversized = True
        try:
            value = "" if oversized else source.decode("utf-8").strip()
        except UnicodeError:
            value = ""
        yield offset, value


def ingest_records(
    store: Store,
    records: Iterable[tuple[int, str]],
    run_id: str,
    month: str,
    batch_size: int = 100,
) -> dict[str, Any]:
    month_bounds(month)
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,80}", run_id):
        raise ValueError("Run ID must be 1-80 safe characters")
    if not 1 <= batch_size <= 1000:
        raise ValueError("Batch size must be 1-1000")
    checkpoint = store.input_progress(run_id)["last_offset"]
    batch: list[tuple[int, str | None, str]] = []

    def flush() -> None:
        valid = [item for _, item, _ in batch if item is not None]
        identifiers = iter(
            store.submit(
                valid,
                generation=run_id,
                principal="batch",
                source_run_id=run_id,
                source_month=month,
            )
        )
        mapped = [
            (offset, next(identifiers) if value is not None else None, state)
            for offset, value, state in batch
        ]
        store.record_inputs(run_id, month, mapped)
        batch.clear()

    for offset, value in records:
        if offset <= checkpoint:
            continue
        try:
            normalized = normalize_url(value)
        except ValueError:
            batch.append((offset, None, "rejected"))
        else:
            batch.append((offset, normalized, "admitted"))
        if len(batch) >= batch_size:
            flush()
    if batch:
        flush()
    return store.input_progress(run_id)


def ingest_file(store: Store, path: Path, run_id: str, month: str) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    store.ensure_run(run_id, digest.hexdigest(), month)
    return ingest_records(store, bounded_lines(path), run_id, month)


def ingest_mysql(
    store: Store,
    dsn: str,
    table_name: str,
    id_column: str,
    url_column: str,
    date_column: str,
    run_id: str,
    month: str,
) -> dict[str, Any]:
    first, following = month_bounds(month)
    engine = sa.create_engine(dsn, pool_pre_ping=True)
    if engine.dialect.name != "mysql":
        engine.dispose()
        raise ValueError("Source must be a read-only MySQL connection")
    try:
        source = sa.Table(table_name, sa.MetaData(), autoload_with=engine)
        identifier, url, timestamp = (
            source.c[id_column],
            source.c[url_column],
            source.c[date_column],
        )
        if not isinstance(identifier.type, sa.Integer):
            raise ValueError("MySQL source ID must be an indexed monotonic integer")
        with engine.connect() as conn:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            filters = (timestamp >= first, timestamp < following)
            bounds = conn.execute(
                sa.select(sa.func.min(identifier), sa.func.max(identifier)).where(*filters)
            ).one()
            minimum = cast(int | None, bounds[0])
            maximum = cast(int | None, bounds[1])
            if minimum is not None and minimum <= 0:
                raise ValueError("MySQL source IDs must be positive")
            fingerprint = url_id(
                json_source_identity(engine.url, table_name, month)
                + f"\0{id_column}\0{url_column}\0{date_column}"
            )
            high_water = store.ensure_run(run_id, fingerprint, month, int(maximum or 0)) or 0

            def rows() -> Iterator[tuple[int, str]]:
                cursor = store.input_progress(run_id)["last_offset"]
                while cursor < high_water:
                    page = conn.execute(
                        sa.select(identifier, url)
                        .where(*filters, identifier > cursor, identifier <= high_water)
                        .order_by(identifier)
                        .limit(100)
                    ).all()
                    if not page:
                        return
                    for record in page:
                        cursor = int(record[0])
                        yield cursor, str(record[1]) if record[1] is not None else ""

            return ingest_records(store, rows(), run_id, month)
    finally:
        engine.dispose()


def json_source_identity(url: sa.engine.URL, table: str, month: str) -> str:
    return f"{url.host}:{url.port}/{url.database}/{table}/{month}"
