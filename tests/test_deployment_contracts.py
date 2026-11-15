from pathlib import Path

import yaml

from crawler_poc.workflow import build_command


def test_argo_fanout_is_bounded_and_commands_are_implemented() -> None:
    path = Path(__file__).parents[1] / "deploy" / "argo" / "crawl-shard.yaml"
    workflow = yaml.safe_load(path.read_text())
    assert workflow["spec"]["parallelism"] == 4
    pipeline = workflow["spec"]["templates"][0]["dag"]["tasks"]
    workers = next(task for task in pipeline if task["name"] == "workers")
    assert workers["withItems"] == [0, 1, 2, 3]
    assert build_command("ingest", "gs://bucket/input", "2026-11", "run") == [
        "ingest",
        "--input",
        "gs://bucket/input",
        "--month",
        "2026-11",
        "--run-id",
        "run",
    ]
    assert build_command("publish", "unused", "2026-11", "run") == ["publish"]
