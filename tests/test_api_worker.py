from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from crawler_poc.api import create_app
from crawler_poc.config import Settings
from crawler_poc.fetching import FetchedPage, FetchError
from crawler_poc.models import Outcome
from crawler_poc.storage import ContentStore, Store
from crawler_poc.worker import Worker

KEY = "test-only-not-a-real-credential-123"


@pytest.fixture
def setup(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'jobs.db'}",
        content_root=tmp_path / "content",
        api_key=KEY,
    )
    store = Store(settings.database_url)
    with TestClient(create_app(settings, store)) as client:
        yield settings, store, client
    store.close()


async def test_real_pipeline_with_fixture_transport(setup) -> None:
    settings, store, client = setup
    assert client.post("/v1/crawls", json={"url": "https://example.com/"}).status_code == 401
    headers = {"X-API-Key": KEY, "Idempotency-Key": "test-run"}
    response = client.post("/v1/crawls", json={"url": "https://example.com/"}, headers=headers)
    identifier = response.json()["job_ids"][0]
    source = (Path(__file__).parent / "fixtures" / "product.html").read_bytes()
    transport = AsyncMock()
    transport.fetch.return_value = FetchedPage("https://example.com/", source, 200, "text/html")
    worker = Worker(settings, store, ContentStore(settings.content_root), transport)
    assert await worker.once()
    result = client.get(f"/v1/crawls/{identifier}", headers={"X-API-Key": KEY}).json()
    assert result["status"] == "terminal"
    assert result["result"]["outcome"] == "success"
    assert result["result"]["page_type"] == "product"
    assert result["result"]["fetch_method"] == "http"
    assert result["result"]["timings_ms"]["total"] >= 0
    assert "json_ld" in result["result"]
    assert "extracted_details_json" in result["result"]["metadata"]
    assert "token" not in result
    url_id = result["url_id"]
    content = client.get(f"/v1/documents/{url_id}/content", headers={"X-API-Key": KEY})
    assert "toaster" in content.text
    assert content.headers["x-content-type-options"] == "nosniff"
    assert client.get("/health/ready").status_code == 200


@pytest.mark.parametrize(
    ("outcome", "reason", "status", "stage"),
    [
        (Outcome.RETRY_EXHAUSTED, "transient_http_status", 503, "fetch"),
        (Outcome.ROBOTS_DISALLOWED, "robots_access_denied", 403, "robots"),
        (Outcome.TOO_LARGE, "decoded_size_limit", 200, "fetch"),
    ],
)
async def test_failure_context_survives_worker_api_and_outbox(
    setup, outcome: Outcome, reason: str, status: int, stage: str
) -> None:
    settings, store, client = setup
    settings.max_attempts = 1
    url = "https://example.com/article?tracking=not-in-diagnostics"
    response = client.post("/v1/crawls", json={"url": url}, headers={"X-API-Key": KEY})
    identifier = response.json()["job_ids"][0]
    failure_url = "https://example.com/robots.txt" if stage == "robots" else url
    transport = AsyncMock()
    transport.fetch.side_effect = FetchError(
        outcome,
        reason,
        retryable=status == 503,
        stage=stage,
        http_status=status,
        url=failure_url,
        content_type="text/html",
        limit_bytes=1024 if outcome == Outcome.TOO_LARGE else None,
        observed_bytes=1025 if outcome == Outcome.TOO_LARGE else None,
    )
    worker = Worker(settings, store, ContentStore(settings.content_root), transport)
    assert await worker.once()
    job = client.get(f"/v1/crawls/{identifier}", headers={"X-API-Key": KEY}).json()
    assert job["status"] == "terminal"
    result = job["result"]
    assert result["http_status"] == status
    assert result["reason"] == reason
    assert result["final_url"] == (None if stage == "robots" else url)
    assert result["metadata"]["failure_stage"] == stage
    assert "tracking" not in result["metadata"]["failure_url"]
    if outcome == Outcome.TOO_LARGE:
        assert result["metadata"]["failure_limit_bytes"] == "1024"
        assert result["metadata"]["failure_observed_bytes"] == "1025"
    batch = store.prepare_batch(100)
    assert batch is not None
    assert batch[1][0]["http_status"] == status
    assert batch[1][0]["metadata"] == result["metadata"]


def test_body_limit_validation_and_idempotency(setup) -> None:
    _, _, client = setup
    headers = {"X-API-Key": KEY, "Idempotency-Key": "same"}
    assert (
        client.post("/v1/crawls", json={"url": "http://127.0.0.1"}, headers=headers).status_code
        == 422
    )
    assert client.post("/v1/crawls", content=b"x" * 70000, headers=headers).status_code == 413
    assert (
        client.post(
            "/v1/crawls", json={"url": "https://example.com/a"}, headers=headers
        ).status_code
        == 202
    )
    assert (
        client.post(
            "/v1/crawls", json={"url": "https://example.com/b"}, headers=headers
        ).status_code
        == 409
    )


def test_api_refuses_insecure_default_configuration(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="API_KEY"):
        create_app(Settings(api_key="", content_root=tmp_path))
