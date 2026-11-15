from pathlib import Path

from crawler_poc.benchmark import ingestion_benchmark
from crawler_poc.evaluation import evaluate


def test_synthetic_corpus_contracts() -> None:
    report = evaluate(Path(__file__).parent / "fixtures")
    assert report["page_type_macro_f1"] == 1
    assert report["title_exact_match_rate"] == 1
    assert all(case["expected_abstention_met"] is not False for case in report["cases"])


def test_streaming_benchmark_accounts_for_every_input() -> None:
    report = ingestion_benchmark(100)
    assert report["progress"]["counts"] == {"admitted": 98, "rejected": 2}
    assert report["network_requests"] == 0
