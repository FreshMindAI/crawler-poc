import os

import pytest

from crawler_poc.lakehouse import bigquery_report, trino_report


@pytest.mark.cloud
@pytest.mark.skipif(
    os.environ.get("CRAWLER_RUN_CLOUD_TESTS") != "1",
    reason="Requires explicit authorization and configured real remote resources",
)
def test_real_trino_bigquery_publication() -> None:
    batch = os.environ["CRAWLER_TEST_BATCH_ID"]
    expected = int(os.environ["CRAWLER_TEST_EXPECTED_ROWS"])
    assert expected > 0
    trino = trino_report(
        os.environ["CRAWLER_TRINO_HOST"],
        os.environ["CRAWLER_TRINO_TABLE"],
        batch,
        os.environ["CRAWLER_TRINO_USER"],
        token=os.environ.get("CRAWLER_TRINO_TOKEN"),
    )
    bigquery = bigquery_report(
        os.environ["CRAWLER_GCP_PROJECT"],
        os.environ["CRAWLER_GCP_LOCATION"],
        os.environ["CRAWLER_BIGQUERY_TABLE"],
        batch,
    )
    assert trino["rows"] == trino["distinct_events"] == expected
    assert bigquery["rows"] == bigquery["distinct_events"] == expected
    assert bigquery["query_job_id"]
