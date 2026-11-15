from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import sqlalchemy as sa

from crawler_poc.ingestion import ingest_mysql
from crawler_poc.storage import Store


@pytest.mark.parametrize("first_id", [0, 1])
def test_mysql_query_contract_uses_month_highwater_and_readonly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first_id: int,
) -> None:
    # SQLite executes the query logic only; this does not emulate MySQL protocol/snapshot behavior.
    source_engine = sa.create_engine(f"sqlite:///{tmp_path / 'source.db'}")
    source = sa.Table(
        "source_urls",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("url", sa.String),
        sa.Column("observed", sa.DateTime),
    )
    source.metadata.create_all(source_engine)
    with source_engine.begin() as conn:
        conn.execute(
            source.insert(),
            [
                {"id": first_id, "url": "https://example.com/a", "observed": datetime(2026, 11, 1)},
                {"id": 2, "url": "invalid", "observed": datetime(2026, 11, 30)},
                {"id": 3, "url": "https://example.com/outside", "observed": datetime(2026, 12, 1)},
            ],
        )
    control = Store(f"sqlite:///{tmp_path / 'control.db'}")
    readonly = Mock()

    @contextmanager
    def connect():
        with source_engine.connect() as connection:
            yield SimpleNamespace(
                execute=connection.execute,
                exec_driver_sql=readonly,
            )

    adapter = SimpleNamespace(
        dialect=SimpleNamespace(name="mysql"),
        connect=connect,
        dispose=Mock(),
        url=sa.engine.make_url("mysql+pymysql://read_only@source.test/input"),
    )
    monkeypatch.setattr(sa, "create_engine", lambda *args, **kwargs: adapter)
    monkeypatch.setattr(sa, "Table", lambda *args, **kwargs: source)
    try:
        if first_id == 0:
            with pytest.raises(ValueError, match="positive"):
                ingest_mysql(
                    control,
                    "operator-dsn",
                    "source_urls",
                    "id",
                    "url",
                    "observed",
                    "run-1",
                    "2026-11",
                )
        else:
            result = ingest_mysql(
                control, "operator-dsn", "source_urls", "id", "url", "observed", "run-1", "2026-11"
            )
            assert result["counts"] == {"admitted": 1, "rejected": 1}
            assert result["last_offset"] == 2
            assert (
                ingest_mysql(
                    control,
                    "operator-dsn",
                    "source_urls",
                    "id",
                    "url",
                    "observed",
                    "run-1",
                    "2026-11",
                )
                == result
            )
        readonly.assert_called_with("SET TRANSACTION READ ONLY")
    finally:
        control.close()
        source_engine.dispose()
