from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crawler_poc.api import create_app
from crawler_poc.config import Settings
from crawler_poc.storage import ContentStore, Store


@pytest.fixture
def ui_client(tmp_path: Path):
    settings = Settings(
        api_key="fixture-only-ui-api-key-12345678",
        database_url=f"sqlite:///{tmp_path / 'jobs.db'}",
        content_root=tmp_path / "objects",
    )
    store = Store(settings.database_url)
    with TestClient(create_app(settings, store)) as client:
        yield client, store, settings
    store.close()


def test_ui_assets_are_public_but_api_stays_protected(ui_client) -> None:
    client, _, settings = ui_client
    assert client.get("/v1/config").json() == {"auth_mode": "api_key"}
    for path, mime in (
        ("/", "text/html"),
        ("/ui/app.css", "text/css"),
        ("/ui/app.js", "javascript"),
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert mime in response.headers["content-type"]
        assert settings.api_key.get_secret_value() not in response.text
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert response.headers["referrer-policy"] == "no-referrer"
    assert client.get("/ui/../api.py").status_code == 404
    assert client.post("/v1/crawls", json={"url": "https://example.com/"}).status_code == 401


def test_job_body_is_authenticated_and_not_latest_generation(ui_client) -> None:
    client, store, settings = ui_client
    headers = {"X-API-Key": settings.api_key.get_secret_value()}
    content = ContentStore(settings.content_root)
    (first,) = store.submit(["https://example.com/"], "first", 5)
    job = store.claim(120)
    store.finish(job, {"outcome": "success", "body_ref": content.put(b"first body")})
    store.submit(["https://example.com/"], "second", 5)
    store.finish(store.claim(120), {"outcome": "success", "body_ref": content.put(b"new body")})
    path = f"/v1/crawls/{first}/content"
    assert client.get(path).status_code == 401
    response = client.get(path + "?offset=0&limit=5", headers=headers)
    assert response.status_code == 200
    assert response.text == "first"
    assert response.headers["content-type"].startswith("text/plain")
    assert client.get(path + "?offset=-1", headers=headers).status_code == 422
    assert client.get("/v1/crawls/missing/content", headers=headers).status_code == 404


def test_job_without_successful_body_returns_not_found(ui_client) -> None:
    client, store, settings = ui_client
    (identifier,) = store.submit(["https://example.com/"], "initial", 5)
    headers = {"X-API-Key": settings.api_key.get_secret_value()}
    path = f"/v1/crawls/{identifier}/content"
    assert client.get(path, headers=headers).status_code == 404
    store.finish(store.claim(120), {"outcome": "target_blocked", "reason": "target_access_denied"})
    assert client.get(path, headers=headers).status_code == 404
