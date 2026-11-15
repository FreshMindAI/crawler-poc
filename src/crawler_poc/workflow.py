import argparse
import os
import sys

from crawler_poc.cli import main


def build_command(operation: str, source: str, month: str, run_id: str) -> list[str]:
    if operation == "ingest":
        return ["ingest", "--input", source, "--month", month, "--run-id", run_id]
    if operation in {"publish", "reconcile"}:
        return [operation]
    raise ValueError("Unsupported workflow operation")


def execute() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["ingest", "publish", "reconcile", "reports"])
    parser.add_argument("--source", required=True)
    parser.add_argument("--month", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.operation == "reports":
        from crawler_poc.config import Settings
        from crawler_poc.lakehouse import bigquery_report, trino_report
        from crawler_poc.storage import Store

        # All six non-secret settings must be supplied before either remote query starts.
        names = [
            "TRINO_HOST",
            "TRINO_TABLE",
            "TRINO_USER",
            "GCP_PROJECT",
            "GCP_LOCATION",
            "BIGQUERY_TABLE",
        ]
        config = {name: os.environ["CRAWLER_" + name] for name in names}
        store = Store(Settings().database_url)
        try:
            batches = store.published_batches(args.run_id)
        finally:
            store.close()
        if not batches:
            raise ValueError("No published data for this run; analytics evidence would be empty")
        for batch, count in batches:
            trino = trino_report(
                config["TRINO_HOST"],
                config["TRINO_TABLE"],
                batch,
                config["TRINO_USER"],
                token=os.environ.get("CRAWLER_TRINO_TOKEN"),
            )
            bigquery = bigquery_report(
                config["GCP_PROJECT"],
                config["GCP_LOCATION"],
                config["BIGQUERY_TABLE"],
                batch,
            )
            if not (
                trino["rows"]
                == trino["distinct_events"]
                == bigquery["rows"]
                == bigquery["distinct_events"]
                == count
            ):
                raise ValueError("Cross-engine publication reconciliation failed")
            import json

            print(json.dumps({"trino": trino, "bigquery": bigquery}, default=str))
        return
    sys.argv = ["crawler", *build_command(args.operation, args.source, args.month, args.run_id)]
    main()


if __name__ == "__main__":
    try:
        execute()
    except Exception as exc:
        print(f"Workflow failed: {type(exc).__name__}; see runbook.", file=sys.stderr)
        sys.exit(1)
