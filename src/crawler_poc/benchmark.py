import json
import platform
import statistics
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lxml import html

from crawler_poc.extraction import extract_page
from crawler_poc.models import normalize_url


def benchmark(records: int, mode: str, fixture: Path) -> dict[str, Any]:
    import psutil

    if not 1 <= records <= 1000000:
        raise ValueError("Records must be 1-1000000")
    source = fixture.read_bytes()
    process = psutil.Process()
    start_rss = process.memory_info().rss
    peak_rss = start_rss
    samples: list[float] = []
    started = time.perf_counter()
    cpu_start = time.process_time()
    for index in range(records):
        begin = time.perf_counter()
        if mode == "url":
            normalize_url(f"https://example.com/items/{index}?variant=1&variant=2")
        elif mode == "parse":
            tree = html.fromstring(source, parser=html.HTMLParser(no_network=True))
            tree.xpath("//title/text()")
        elif mode == "extract":
            extract_page(source, "https://example.com/item")
        else:
            raise ValueError("Mode must be url, parse or extract")
        if index % max(1, records // 1000) == 0:
            samples.append(time.perf_counter() - begin)
            peak_rss = max(peak_rss, process.memory_info().rss)
    elapsed = time.perf_counter() - started
    ordered = sorted(samples)
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "records": records,
        "mode": mode,
        "seconds": elapsed,
        "records_per_second": records / elapsed,
        "cpu_seconds": time.process_time() - cpu_start,
        "rss_start_bytes": start_rss,
        "rss_peak_sampled_bytes": peak_rss,
        "sample_latency_p50_ms": statistics.median(samples) * 1000,
        "sample_latency_p95_ms": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] * 1000,
        "network_requests": 0,
        "fixture": fixture.name,
        "distinct_templates": 1,
        "limitations": "One repeated synthetic template; stage benchmark, not end-to-end capacity.",
    }


def ingestion_benchmark(records: int) -> dict[str, Any]:
    import hashlib

    import psutil

    from crawler_poc.ingestion import bounded_lines, ingest_records
    from crawler_poc.storage import Store

    if not 1 <= records <= 1000000:
        raise ValueError("Records must be 1-1000000")
    process = psutil.Process()
    with TemporaryDirectory(prefix="crawler-benchmark-") as directory:
        root = Path(directory)
        source = root / "input.txt"
        with source.open("w", encoding="ascii", newline="\n") as stream:
            for index in range(records):
                stream.write(
                    "invalid\n" if index % 97 == 0 else f"https://example.com/item/{index % 1000}\n"
                )
        store = Store(f"sqlite:///{root / 'jobs.db'}")
        start_rss = peak_rss = process.memory_info().rss
        started, cpu_started = time.perf_counter(), time.process_time()
        try:
            with source.open("rb") as binary:
                fingerprint = hashlib.file_digest(binary, "sha256").hexdigest()
            store.ensure_run("benchmark", fingerprint, "2026-11")

            def rows() -> Any:
                nonlocal peak_rss
                for offset, value in bounded_lines(source):
                    if offset % 1000 == 0:
                        peak_rss = max(peak_rss, process.memory_info().rss)
                    yield offset, value

            progress = ingest_records(store, rows(), "benchmark", "2026-11")
            counts = store.counts()
            elapsed = time.perf_counter() - started
            return {
                "mode": "ingest",
                "records": records,
                "seconds": elapsed,
                "records_per_second": records / elapsed,
                "cpu_seconds": time.process_time() - cpu_started,
                "rss_start_bytes": start_rss,
                "rss_peak_sampled_bytes": peak_rss,
                "progress": progress,
                "jobs": counts,
                "network_requests": 0,
                "python": platform.python_version(),
                "platform": platform.platform(),
                "limitations": (
                    "Streaming local file, SQLite, 1000 distinct URL variants with duplicates "
                    "and invalid rows. Admission/accounting only; no HTTP crawl/publication."
                ),
            }
        finally:
            store.close()


def save_report(report: dict[str, Any], output: Path | None) -> None:
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
