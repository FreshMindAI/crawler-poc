# Billion-URL collection and large-read design

This is a production design and capacity model, **not measured production
capacity**. The implemented POC uses a small durable SQL queue; it must not be
mistaken for a billion-row frontier.

## Data path

```text
monthly text/MySQL snapshot -> immutable bounded source manifests + alias ledger
  -> partitioned durable frontier -> host-aware bounded Python worker pools
  -> guarded HTTP -> metadata/body + local NLP
  -> private compressed content objects + transactional terminal outbox
  -> one publication/maintenance ownership domain -> Iceberg v2 / Parquet
  -> Trino + BigQuery analytical consumers

terminal events -> partitioned latest-success projection -> cache -> read API
Argo: bounded manifest pages / fixed pools / commit / reconcile / report
```

The POC implements the stages, not the production partitioned queue/cache or
manifest scheduler. Source aliases are disk-backed. A single PostgreSQL primary
and global admission advisory lock deliberately trade POC simplicity for bounded
throughput; replace them only after a workload-specific partitioning experiment.

Shard stable work identity by URL hash, retaining origin as a scheduling key.
Use durable per-origin ownership and central/partitioned politeness budgets so
horizontal scaling does not multiply target-site request rates. A hot origin
must not block unrelated origins; add fair per-origin frontiers rather than
letting hundreds of workers wait behind the same domain. The POC's shared lease
enforces pacing but **does not implement production host-fair scheduling**.

Input fingerprint/month, job generation, observed UTC timestamp, publication
batch and Iceberg snapshot are distinct identities. MySQL should have a covering
index supporting `(source_timestamp, numeric_id)` or a verified monthly partition
and ID index; test the actual query plan. Month filtering uses declared UTC
source dates and a pinned high watermark; mutable/re-keyed rows require a source
snapshot/CDC design, not blind restart of this adapter.

## Capacity worksheet

Let N be input rows, v the valid fraction, d the duplicate fraction of valid rows,
A measured attempts per unique URL, W the processing window in seconds, s bytes
per wire response, c CPU-seconds per extraction, u target CPU utilization,
and h_i the allowed fetch rate for origin i.

```text
U = N * v * (1 - d)
required terminal rate = U / W
attempt rate = U * A / W
network bytes = U * A * s
CPU cores >= terminal rate * c / u
origin i completion time >= assigned_attempts_i / h_i
total wall time >= max(origin completion bounds, CPU, network, storage bounds)
```

Illustration only: 1 billion input rows, v=0.98, d=0.20 yield 784 million unique
jobs. At a hypothetical agreed 30-day window, this requires about 302.5 terminal
jobs/s before retries. This is arithmetic, **not a promise**; domain skew can
make the window impossible even with more compute. The tiny repeated-template
benchmark cannot supply representative c, s, failure rates or host distribution.

Use RSS distributions at fixed concurrency, response-size percentiles and native
parser amplification to size pods. Separate I/O concurrency from CPU parse/NLP
capacity. The current thread offload keeps the API loop responsive but does not
remove Python's GIL for YAKE; a process pool or bounded CPU worker tier is a
profiling-led alternative before Rust.

## Storage and analytical access

Raw HTML and clean text are private content-addressed compressed objects.
Metadata rows contain references, bounded previews and provenance. Deduplicate
identical bytes without assuming identical URLs have identical rights or retention.
Apply lifecycle policy only after lawful retention/deletion requirements and
references across snapshots/backups are understood.

Iceberg provides real cataloged snapshots, not just Parquet paths. The current
writer partitions by observed UTC day. Add a bounded bucket transform only after
measuring distribution and query behavior; never partition per URL/domain.
POC batches of up to 10,000 rows avoid per-URL commits but can still produce small
files. Production should tune to measured compressed sizes, typically testing
128-512 MiB data files, and schedule owned compaction/manifest maintenance.
No automatic destructive snapshot/orphan cleanup is implemented.

Trino handles interactive/ad-hoc analytical queries; BigQuery reads the supported
externally owned table or an explicitly designed projection. Visibility must be
compared for the same publication/snapshot definition. Read APIs use the latest
projection/key-value store and cache, **not an analytical scan per request**.

For peak R read requests/s, cache hit fraction H and payload p:
backing reads = R*(1-H), and response bandwidth = R*p. Partition the serving key
space by URL hash, protect hot keys, use bounded body pagination/object reads,
and load-test the actual auth/gateway/database path. No million-RPS proof exists.

## Cost model and sources

No cloud bill or fixed price is fabricated before provider/region/quotas are
approved. Record dated regional unit prices and a budget owner using:

- Google Cloud pricing calculator: https://cloud.google.com/products/calculator
- BigQuery pricing: https://cloud.google.com/bigquery/pricing
- GCS pricing: https://cloud.google.com/storage/pricing
- Azure calculator: https://azure.microsoft.com/pricing/calculator/

```text
compute = measured worker CPU-hours and serving/catalog/Trino/Argo node-hours * rates
storage = retained compressed raw + clean + metadata + snapshots + backups * GB-month rates
operations = object reads/writes/listing + catalog/database operations
transfer = applicable outbound/cross-region/cross-cloud bytes * transfer rates
queries = billed BigQuery scans/slots + Trino worker resources
total = above + monitoring + fixed platform costs + retry/compaction headroom
```

Keep GB/GiB, decimal billing units and compression ratios explicit. Account for
Azure-to-GCP transfer and identity if choosing Azure hosting. On-demand query caps,
partition/column pruning, budgets and service quotas reduce risk; a SQL query cap
is not an account-wide spending cap.

## Reliability, SLO and SLA

At-least-once delivery with stable IDs, fencing, an outbox and replay-verified
publication gives testable duplicate-free effective results, not distributed
exactly-once execution. Persist progress outside pods; isolate failed batches and
source snapshots. Configure backup/restore drills and failure domains on the real
platform before claiming availability.

Proposed API SLO: 99.9% eligible authenticated requests return a valid response
without service-side failure over a rolling 30-day window. Define request
eligibility, dependency errors and maintenance with the owner. A legitimate
robots/404 outcome is not automatically an API availability failure. At constant
traffic, 0.1% is roughly 43.2 minutes of a 30-day period, but use request-based
error budgets for the stated SLI rather than converting blindly to downtime.

Proposed controlled warm metadata-read p95: 250 ms on an agreed resource profile.
Crawl freshness and publication lag targets require the source volume/window,
host mix and owner agreement; record oldest eligible-job age and acknowledged
analytical watermark. None of these targets is an observed SLO or contractual SLA.

Alert on sustained queue age growth, no progress, excessive retries/lease expiry,
outbox backlog, commit failures, reconciliation mismatches, memory pressure,
read latency/error-budget burn and budget/scan anomalies. Implemented metrics are
queue-state counts, unpublished count and oldest-job age; richer timings/outcome
histograms, distributed traces and platform alerts remain remote hardening work.
