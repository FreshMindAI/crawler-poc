import json
from pathlib import Path

import pytest

from crawler_poc.fetching import FetchError
from crawler_poc.lakehouse import IcebergPublisher, local_catalog, quoted_table
from crawler_poc.models import Outcome
from crawler_poc.storage import Store


def test_failure_response_context_publishes_without_schema_change(tmp_path: Path) -> None:
    pytest.importorskip("pyiceberg")
    store = Store(f"sqlite:///{tmp_path / 'jobs.db'}")
    catalog = local_catalog(tmp_path / "iceberg")
    try:
        store.submit(["https://example.com/article"])
        job = store.claim(30)
        assert job
        error = FetchError(
            Outcome.ROBOTS_DISALLOWED,
            "robots_access_denied",
            stage="robots",
            http_status=403,
            url="https://example.com/robots.txt",
            content_type="text/html",
        )
        assert store.finish(job, error.as_result())
        publisher = IcebergPublisher(catalog, "crawler.crawl_events")
        assert publisher.publish(store)["published"] == 1
        row = publisher.table().scan().to_arrow().to_pylist()[0]
        assert row["http_status"] == 403
        assert row["final_url"] is None
        assert json.loads(row["metadata_json"]) == {
            "failure_stage": "robots",
            "failure_url": "https://example.com/robots.txt",
        }
    finally:
        catalog.engine.dispose()
        store.close()


def test_real_iceberg_commit_and_crash_replay(tmp_path: Path) -> None:
    pytest.importorskip("pyiceberg")
    store = Store(f"sqlite:///{tmp_path / 'jobs.db'}")
    try:
        store.submit(["https://example.com/"])
        job = store.claim(30)
        assert job
        assert store.finish(
            job,
            {
                "outcome": "success",
                "title": "Unicode \u00e9",
                "topics": [
                    {
                        "phrase": "camping",
                        "rank": 1,
                        "raw_score": 0.1,
                        "method": "yake",
                        "evidence": "body",
                    }
                ],
            },
        )
        publisher = IcebergPublisher(local_catalog(tmp_path / "iceberg"), "crawler.crawl_events")

        def crash() -> None:
            raise RuntimeError("simulated crash after Iceberg commit")

        with pytest.raises(RuntimeError, match="simulated crash"):
            publisher.publish(store, after_commit=crash)
        assert store.counts()["unpublished"] == 1
        result = publisher.publish(store)
        assert result["recovered"] is True
        assert result["published"] == 1
        assert store.counts()["unpublished"] == 0
        rows = publisher.table().scan().to_arrow().to_pylist()
        assert len(rows) == 1
        assert rows[0]["title"] == "Unicode \u00e9"
        assert rows[0]["topics"][0]["phrase"] == "camping"
        assert str(publisher.table().spec().fields[0].transform) == "day"
        assert publisher.publish(store) == {"published": 0}
    finally:
        store.close()


def test_sql_identifiers_cannot_inject() -> None:
    assert quoted_table("iceberg.crawler.crawl_events") == '"iceberg"."crawler"."crawl_events"'
    with pytest.raises(ValueError):
        quoted_table("dataset.table; DROP TABLE secret")


def test_bigquery_sdk_config_uses_bound_value_and_scan_cap(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from google.cloud import bigquery

    from crawler_poc.lakehouse import bigquery_report

    client = MagicMock()
    client.__enter__.return_value = client
    job = client.query.return_value
    job.result.return_value = [bigquery.table.Row((3, 3), {"rows": 0, "distinct_events": 1})]
    job.job_id, job.total_bytes_processed = "unit-test-query", 123
    monkeypatch.setattr(bigquery, "Client", lambda **kwargs: client)
    batch = "batch' OR '1'='1"
    report = bigquery_report("unit-test-project", "US", "dataset.events", batch)
    sql = client.query.call_args.args[0]
    config = client.query.call_args.kwargs["job_config"]
    assert batch not in sql and "@batch_id" in sql
    assert config.query_parameters[0].value == batch
    assert config.maximum_bytes_billed == 100 * 1024 * 1024
    assert int(config.job_timeout_ms) == 60000
    assert report["rows"] == report["distinct_events"] == 3


def test_trino_client_uses_https_and_bound_value(monkeypatch) -> None:
    from unittest.mock import MagicMock

    import trino.dbapi

    from crawler_poc.lakehouse import trino_report

    connection = MagicMock()
    connection.cursor.return_value.fetchone.return_value = (2, 2)
    connect = MagicMock(return_value=connection)
    monkeypatch.setattr(trino.dbapi, "connect", connect)
    batch = "batch' OR '1'='1"
    report = trino_report("unit-test.invalid", "iceberg.crawler.events", batch, "unit-test")
    sql, parameters = connection.cursor.return_value.execute.call_args.args
    assert batch not in sql and parameters == [batch]
    assert connect.call_args.kwargs["http_scheme"] == "https"
    assert report["rows"] == report["distinct_events"] == 2
    connection.close.assert_called_once()
