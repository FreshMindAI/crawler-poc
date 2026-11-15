from pathlib import Path

import pytest

from crawler_poc.ingestion import bounded_lines, ingest_file, month_bounds
from crawler_poc.storage import Store


def test_stream_resume_duplicate_and_changed_source(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    source.write_text("https://example.com/a\nbad\nhttps://example.com/a\nhttps://example.org/b\n")
    store = Store(f"sqlite:///{tmp_path / 'state.db'}")
    try:
        result = ingest_file(store, source, "run-1", "2026-11")
        assert result["counts"] == {"admitted": 2, "duplicate": 1, "rejected": 1}
        assert ingest_file(store, source, "run-1", "2026-11") == result
        source.write_text("https://changed.example/\n")
        with pytest.raises(ValueError, match="different source"):
            ingest_file(store, source, "run-1", "2026-11")
    finally:
        store.close()


def test_oversized_input_is_one_rejected_record(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    source.write_bytes(b"x" * 100000 + b"\nhttps://example.com/\n")
    assert list(bounded_lines(source)) == [(1, ""), (2, "https://example.com/")]
    assert month_bounds("2026-12")[1].isoformat() == "2027-01-01"
    with pytest.raises(ValueError):
        month_bounds("2026-13")
