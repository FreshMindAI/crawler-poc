import json
from pathlib import Path
from typing import Any

from crawler_poc.extraction import extract_page


def evaluate(corpus: Path) -> dict[str, Any]:
    labels = json.loads((corpus / "labels.json").read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    pairs: list[tuple[str, str]] = []
    for case in labels["cases"]:
        page = extract_page((corpus / case["file"]).read_bytes(), "https://example.com/fixture")
        pairs.append((case["page_type"], page.page_type))
        hits = sum(
            any(term in topic.phrase.lower() for term in case["topic_terms"])
            for topic in page.topics
        )
        results.append(
            {
                "fixture": case["file"],
                "expected_type": case["page_type"],
                "actual_type": page.page_type,
                "title_match": page.title == case["title"],
                "topics": [topic.phrase for topic in page.topics],
                "warnings": page.warnings,
                "topic_term_match_fraction": hits / len(page.topics) if page.topics else None,
                "expected_abstention_met": not page.topics if case.get("no_topics") else None,
            }
        )
    scores = []
    for label in sorted({expected for expected, _ in pairs}):
        tp = sum(expected == actual == label for expected, actual in pairs)
        fp = sum(expected != label and actual == label for expected, actual in pairs)
        fn = sum(expected == label and actual != label for expected, actual in pairs)
        scores.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0)
    return {
        "corpus_size": len(results),
        "page_type_macro_f1": sum(scores) / len(scores),
        "title_exact_match_rate": sum(item["title_match"] for item in results) / len(results),
        "provenance": labels["provenance"],
        "limitations": (
            "Tiny synthetic regression corpus. Topic term overlap is a lexical proxy, "
            "not human precision@k, nDCG or generalization evidence."
        ),
        "cases": results,
    }
