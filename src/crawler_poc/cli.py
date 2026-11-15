import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from crawler_poc.config import Settings
from crawler_poc.storage import ContentStore, DatabaseOriginGate, Store


async def run_workers(settings: Settings, store: Store, drain: bool) -> None:
    from crawler_poc.fetching import SafeFetcher
    from crawler_poc.worker import Worker

    content = ContentStore(settings.object_uri or settings.content_root)
    gate = DatabaseOriginGate(
        store, settings.origin_delay, max(settings.lease_seconds, settings.request_timeout + 10)
    )
    async with SafeFetcher(settings, gate) as fetcher:
        worker = Worker(settings, store, content, fetcher)
        await asyncio.gather(*(worker.run(drain) for _ in range(settings.workers)))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Safe URL metadata/topic crawler POC")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="Initialize the configured control database")
    serve = commands.add_parser("serve", help="Run the API; workers run separately")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    worker = commands.add_parser("worker", help="Run durable workers")
    worker.add_argument("--drain", action="store_true", help="Exit when the entire queue is idle")
    ingest = commands.add_parser("ingest", help="Stream a local or GCS URL file")
    ingest.add_argument("--input", required=True)
    ingest.add_argument("--run-id", required=True)
    ingest.add_argument("--month", required=True)
    mysql = commands.add_parser("ingest-mysql", help="Read an immutable monthly MySQL source")
    mysql.add_argument("--dsn-env", default="CRAWLER_SOURCE_MYSQL_DSN")
    for field in ("table", "id-column", "url-column", "date-column", "run-id", "month"):
        mysql.add_argument("--" + field, required=True)
    publish = commands.add_parser("publish", help="Publish real Iceberg batches")
    publish.add_argument("--catalog", default="default")
    publish.add_argument("--table", default="crawler.crawl_events")
    publish.add_argument("--local", type=Path, help="Local SQL catalog/files; no servers")
    publish.add_argument("--batch-size", type=int, default=1000)
    commands.add_parser("reconcile", help="Fail if work or outbox publication is incomplete")
    for name in ("trino-report", "bigquery-report"):
        report = commands.add_parser(name, help="Run a real read-only publication reconciliation")
        report.add_argument("--table", required=True)
        report.add_argument("--batch-id", required=True)
        if name == "trino-report":
            report.add_argument("--host", required=True)
            report.add_argument("--user", required=True)
            report.add_argument("--port", type=int, default=443)
        else:
            report.add_argument("--project", required=True)
            report.add_argument("--location", required=True)
    bench = commands.add_parser("benchmark", help="Run a no-network stage microbenchmark")
    bench.add_argument("--records", type=int, default=10000)
    bench.add_argument("--mode", choices=["url", "parse", "extract", "ingest"], default="parse")
    bench.add_argument("--fixture", type=Path, default=Path("tests/fixtures/product.html"))
    bench.add_argument("--output", type=Path)
    evaluation = commands.add_parser("evaluate", help="Evaluate the synthetic regression corpus")
    evaluation.add_argument("--corpus", type=Path, default=Path("tests/fixtures"))
    evaluation.add_argument("--output", type=Path)
    return root


def execute(args: argparse.Namespace) -> Any:
    if args.command == "benchmark":
        from crawler_poc.benchmark import benchmark, ingestion_benchmark, save_report

        report = (
            ingestion_benchmark(args.records)
            if args.mode == "ingest"
            else benchmark(args.records, args.mode, args.fixture)
        )
        save_report(report, args.output)
        return None
    if args.command == "evaluate":
        from crawler_poc.benchmark import save_report
        from crawler_poc.evaluation import evaluate

        save_report(evaluate(args.corpus), args.output)
        return None
    if args.command == "trino-report":
        from crawler_poc.lakehouse import trino_report

        return trino_report(
            args.host,
            args.table,
            args.batch_id,
            args.user,
            args.port,
            os.environ.get("CRAWLER_TRINO_TOKEN"),
        )
    if args.command == "bigquery-report":
        from crawler_poc.lakehouse import bigquery_report

        return bigquery_report(args.project, args.location, args.table, args.batch_id)
    settings = Settings()
    if args.command == "serve":
        import uvicorn

        from crawler_poc.api import create_app

        uvicorn.run(create_app(settings), host=args.host, port=args.port, access_log=False)
        return None
    store = Store(settings.database_url, settings.max_pending_jobs)
    try:
        if args.command == "init-db":
            return {"status": "initialized", "backend": store.engine.dialect.name}
        if args.command == "worker":
            asyncio.run(run_workers(settings, store, args.drain))
            return store.counts()
        if args.command == "ingest":
            from crawler_poc.ingestion import ingest_file, ingest_records

            if args.input.startswith("gs://"):
                import io
                from urllib.parse import urlsplit

                from google.cloud.storage import Client

                from crawler_poc.ingestion import bounded_stream
                from crawler_poc.models import url_id

                source = urlsplit(args.input)
                blob = Client().bucket(source.netloc).blob(source.path.lstrip("/"))
                blob.reload()
                fingerprint = url_id(f"{args.input}:{blob.generation}:{blob.size}")
                store.ensure_run(args.run_id, fingerprint, args.month)
                with blob.open("rb", chunk_size=256 * 1024) as raw:
                    stream = io.BufferedReader(raw)
                    return ingest_records(store, bounded_stream(stream), args.run_id, args.month)
            return ingest_file(store, Path(args.input), args.run_id, args.month)
        if args.command == "ingest-mysql":
            from crawler_poc.ingestion import ingest_mysql

            dsn = os.environ.get(args.dsn_env)
            if not dsn:
                raise ValueError("Set the source DSN environment variable; do not pass credentials")
            return ingest_mysql(
                store,
                dsn,
                args.table,
                args.id_column,
                args.url_column,
                args.date_column,
                args.run_id,
                args.month,
            )
        if args.command == "publish":
            from pyiceberg.catalog import load_catalog

            from crawler_poc.lakehouse import IcebergPublisher, local_catalog

            catalog = local_catalog(args.local) if args.local else load_catalog(args.catalog)
            publisher = IcebergPublisher(catalog, args.table)
            published = 0
            last: dict[str, Any] = {}
            try:
                while True:
                    last = publisher.publish(store, args.batch_size)
                    if not last["published"]:
                        break
                    published += last["published"]
                    print(json.dumps(last))
            finally:
                if args.local:
                    engine = getattr(catalog, "engine", None)
                    if engine is not None:
                        engine.dispose()
            return {"published_total": published}
        if args.command == "reconcile":
            counts = store.counts()
            if counts.get("queued", 0) or counts.get("running", 0) or counts["unpublished"]:
                raise ValueError("Queue or analytical publication is incomplete")
            return {"status": "operational_reconciliation_passed", "counts": counts}
        raise ValueError("Unknown command")
    finally:
        store.close()


def main() -> None:
    args = parser().parse_args()
    try:
        value = execute(args)
        if value is not None:
            print(json.dumps(value, indent=2, default=str))
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        # Exception messages from drivers may contain DSNs, URLs or credentials.
        print(
            f"Command failed: {type(exc).__name__}; inspect configuration and runbook.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
