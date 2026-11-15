import os

import pytest


@pytest.fixture(autouse=True)
def isolate_core_configuration(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    if request.node.get_closest_marker("cloud"):
        return
    for name in list(os.environ):
        if name.startswith(("CRAWLER_", "PYICEBERG_")):
            monkeypatch.delenv(name)
