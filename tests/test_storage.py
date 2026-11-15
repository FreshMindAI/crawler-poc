import time
from pathlib import Path

import pytest

from crawler_poc.storage import ContentStore, IdempotencyConflict, Store


@pytest.fixture
def store(tmp_path: Path):
    value = Store(f"sqlite:///{tmp_path / 'jobs.db'}")
    yield value
    value.close()


def test_idempotency_payload_conflict_and_replay(store: Store) -> None:
    ids = store.submit(["https://example.com/a"] * 2, key="request")
    assert ids[0] == ids[1]
    assert store.submit(["https://example.com/a"] * 2, key="request") == ids
    with pytest.raises(IdempotencyConflict):
        store.submit(["https://example.com/b"], key="request")
    assert store.counts()["queued"] == 1


def test_expired_worker_is_fenced_and_outbox_is_atomic(store: Store) -> None:
    identifier = store.submit(["https://example.com/"])[0]
    first = store.claim(-1)
    assert first
    second = store.claim(30)
    assert second and second["token"] > first["token"]
    assert not store.finish(first, {"outcome": "success"})
    assert store.finish(second, {"outcome": "success", "title": "current"})
    assert store.get_job(identifier)["result"]["title"] == "current"
    batch = store.prepare_batch()
    assert batch and len(batch[1]) == 1
    assert store.prepare_batch()[0] == batch[0]
    store.acknowledge(batch[0], "123")
    assert store.prepare_batch() is None


def test_cancel_invalidates_worker(store: Store) -> None:
    identifier = store.submit(["https://example.com/"])[0]
    job = store.claim(30)
    assert store.cancel(identifier)
    assert job and not store.finish(job, {"outcome": "success"})
    assert store.get_job(identifier)["result"]["outcome"] == "canceled"


def test_origin_lease_coordinates_store_instances(store: Store) -> None:
    assert store.acquire_origin("https://example.com", "first", 30)
    assert not store.acquire_origin("https://example.com", "second", 30)
    store.release_origin("https://example.com", "wrong", 0)
    assert not store.acquire_origin("https://example.com", "second", 30)
    store.release_origin("https://example.com", "first", 0.01)
    time.sleep(0.02)
    assert store.acquire_origin("https://example.com", "second", 30)


def test_content_hashes_and_path_safety(tmp_path: Path) -> None:
    content = ContentStore(tmp_path)
    key = content.put(b"hello")
    assert content.put(b"hello") == key
    assert content.get(key) == b"hello"
    with pytest.raises(ValueError):
        content.get("../../outside")


def test_concurrent_claim_and_finish_retains_unique_events(store: Store) -> None:
    from concurrent.futures import ThreadPoolExecutor

    store.submit([f"https://example.com/{number}" for number in range(20)])

    def consume() -> None:
        while job := store.claim(30):
            assert store.finish(job, {"outcome": "not_found"})

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: consume(), range(4)))
    assert store.counts() == {"terminal": 20, "unpublished": 20}
    batch = store.prepare_batch(100)
    assert batch and len({row["event_id"] for row in batch[1]}) == 20


def test_unpublished_events_apply_admission_backpressure(tmp_path: Path) -> None:
    from crawler_poc.storage import CapacityExceeded

    store = Store(f"sqlite:///{tmp_path / 'budget.db'}", max_pending=1)
    try:
        store.submit(["https://example.com/first"])
        job = store.claim(30)
        assert job and store.finish(job, {"outcome": "not_found"})
        with pytest.raises(CapacityExceeded):
            store.submit(["https://example.com/second"])
        batch = store.prepare_batch()
        assert batch
        store.acknowledge(batch[0], "test-snapshot")
        assert store.submit(["https://example.com/second"])
    finally:
        store.close()
