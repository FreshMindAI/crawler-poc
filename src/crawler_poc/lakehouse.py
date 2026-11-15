import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from crawler_poc.storage import Store


def arrow_schema() -> Any:
    import pyarrow as pa

    topic = pa.struct(
        [
            pa.field("phrase", pa.string()),
            pa.field("rank", pa.int32()),
            pa.field("raw_score", pa.float64()),
            pa.field("method", pa.string()),
            pa.field("evidence", pa.string()),
        ]
    )
    return pa.schema(
        [
            pa.field("schema_version", pa.int32()),
            *[
                pa.field(name, pa.string())
                for name in (
                    "event_id",
                    "job_id",
                    "url_id",
                    "normalized_url",
                    "generation",
                    "run_id",
                    "source_month",
                    "publish_batch_id",
                )
            ],
            pa.field("observed_at", pa.timestamp("us", tz="UTC")),
            *[
                pa.field(name, pa.string())
                for name in (
                    "outcome",
                    "reason",
                    "title",
                    "description",
                    "page_type",
                    "language",
                    "final_url",
                    "content_type",
                    "canonical_candidate",
                    "normalization_version",
                    "fetcher_version",
                    "metadata_json",
                    "body_ref",
                    "raw_ref",
                    "body_preview",
                    "extractor_version",
                    "classifier_version",
                )
            ],
            pa.field("attempt_count", pa.int32()),
            pa.field("http_status", pa.int32()),
            pa.field("raw_bytes", pa.int64()),
            pa.field("body_characters", pa.int64()),
            *[
                pa.field(name, pa.list_(pa.string()))
                for name in ("headings", "structured_types", "warnings")
            ],
            pa.field("topics", pa.list_(topic)),
        ]
    )


def local_catalog(directory: Path) -> Any:
    from pyiceberg.catalog.sql import SqlCatalog

    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    warehouse = directory / "warehouse"
    # PyIceberg 0.11 passes /C:/ from canonical file URIs unchanged to Windows Arrow.
    location = f"file://{warehouse.as_posix()}" if os.name == "nt" else warehouse.as_uri()
    return SqlCatalog(
        "local",
        uri=f"sqlite:///{directory / 'catalog.db'}",
        warehouse=location,
    )


def _validate_table(table: str) -> None:
    if not re.fullmatch(r"[a-zA-Z_]\w*\.[a-zA-Z_]\w*", table):
        raise ValueError("Iceberg table must be namespace.table")


class IcebergPublisher:
    def __init__(self, catalog: Any, table_name: str) -> None:
        _validate_table(table_name)
        self.catalog, self.table_name = catalog, table_name

    def table(self) -> Any:
        from pyiceberg.exceptions import NamespaceAlreadyExistsError, NoSuchTableError

        try:
            return self.catalog.load_table(self.table_name)
        except NoSuchTableError:
            try:
                self.catalog.create_namespace(self.table_name.split(".")[0])
            except NamespaceAlreadyExistsError:
                pass
            table = self.catalog.create_table(
                self.table_name,
                schema=arrow_schema(),
                properties={"format-version": "2", "write.parquet.compression-codec": "zstd"},
            )
            with table.update_spec() as update:
                update.add_field("observed_at", "day")
            return table

    def publish(self, store: Store, limit: int = 1000, after_commit: Any = None) -> dict[str, Any]:
        import pyarrow as pa
        from pyiceberg.expressions import EqualTo, Reference
        from pyiceberg.expressions.literals import literal

        if not 1 <= limit <= 10000:
            raise ValueError("Publication batch must be 1-10000")
        batch = store.prepare_batch(limit)
        if batch is None:
            return {"published": 0}
        batch_id, records = batch
        table = self.table()
        predicate = EqualTo(term=Reference("publish_batch_id"), value=literal(batch_id))
        expected = sorted(record["event_id"] for record in records)
        existing = sorted(
            table.scan(row_filter=predicate)
            .select("event_id")
            .to_arrow()
            .column("event_id")
            .to_pylist()
        )
        if existing and existing != expected:
            raise ValueError("Publication identity collision/partial publication; reconcile first")
        if not existing:
            normalized = []
            for record in records:
                import json

                mapped = {name: record.get(name) for name in arrow_schema().names}
                mapped.update(
                    publish_batch_id=batch_id,
                    observed_at=datetime.fromtimestamp(record["observed_at"], UTC),
                    topics=record.get("topics", []),
                    metadata_json=json.dumps(record.get("metadata", {}), sort_keys=True),
                )
                normalized.append(mapped)
            data = pa.Table.from_pylist(normalized, schema=arrow_schema())
            # Predicate overwrite makes the logical publication replay-safe, unlike blind append.
            table.overwrite(
                data,
                overwrite_filter=predicate,
                snapshot_properties={"crawler.publish_batch_id": batch_id},
            )
        snapshot = table.current_snapshot()
        assert snapshot is not None
        if after_commit:
            after_commit()
        store.acknowledge(batch_id, str(snapshot.snapshot_id))
        return {
            "published": len(records),
            "batch_id": batch_id,
            "snapshot_id": snapshot.snapshot_id,
            "metadata_location": table.metadata_location,
            "recovered": bool(existing),
        }


def quoted_table(value: str, bigquery: bool = False) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z_][A-Za-z0-9_]*){1,2}", value):
        raise ValueError("Invalid qualified table identifier")
    return f"`{value}`" if bigquery else ".".join(f'"{part}"' for part in value.split("."))


def trino_report(
    host: str,
    table: str,
    batch_id: str,
    user: str,
    port: int = 443,
    token: str | None = None,
) -> dict[str, Any]:
    import trino.auth
    import trino.dbapi

    connection = trino.dbapi.connect(
        host=host,
        port=port,
        http_scheme="https",
        user=user,
        request_timeout=30,
        max_attempts=3,
        auth=trino.auth.JWTAuthentication(token) if token else None,
    )
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT count(*), count(DISTINCT event_id) FROM {quoted_table(table)} "
            "WHERE publish_batch_id = ?",
            [batch_id],
        )
        count, distinct = cursor.fetchone()
        return {"rows": count, "distinct_events": distinct, "batch_id": batch_id}
    finally:
        connection.close()


def bigquery_report(
    project: str,
    location: str,
    table: str,
    batch_id: str,
    maximum_bytes_billed: int = 100 * 1024 * 1024,
) -> dict[str, Any]:
    from google.cloud import bigquery

    with bigquery.Client(project=project, location=location) as client:
        config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("batch_id", "STRING", batch_id)],
            maximum_bytes_billed=maximum_bytes_billed,
            job_timeout_ms=60000,
        )
        job = client.query(
            f"SELECT count(*) AS rows, count(DISTINCT event_id) AS distinct_events "
            f"FROM {quoted_table(table, True)} WHERE publish_batch_id = @batch_id",
            job_config=config,
        )
        row = next(iter(job.result(timeout=60)))
        return {
            "rows": row["rows"],
            "distinct_events": row["distinct_events"],
            "batch_id": batch_id,
            "query_job_id": job.job_id,
            "bytes_processed": job.total_bytes_processed,
        }
