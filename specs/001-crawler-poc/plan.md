# Technical plan and architecture

Status: selected POC architecture, partially implemented and locally verified.
See `spec.md` D-027 through D-055 and `docs\submission-manifest.md` for the
implemented subset and explicit remote/public release gaps.

## 1. Component boundaries

| Component | Responsibility | Not responsible for |
|---|---|---|
| API/admission | Validate requests, authorize, apply quotas/idempotency and return jobs/results | Running unbounded crawls inside request handlers |
| Optional web workspace | Same-origin, bundled static UI for authenticated job submission/monitoring and exact-job results | Running a worker, persisting API keys or executing extracted HTML |
| Input readers | Stream text/MySQL rows, checkpoint and emit bounded source manifests | Materializing a billion-row list or interpreting reporting month as historical HTML |
| Control/serving store | Durable job/lease state, origin state, aliases, latest results and publication ledger | Being the sole production analytical store |
| Fetch workers/pipeline | Public-destination checks, robots, origin pacing, bounded HTTP and opt-in guarded JS-shell rendering | Recursive discovery, unrestricted browser sessions or bypass |
| Extraction/classification | Metadata precedence, readable body, page-type rules and local ranked topics | Remote extraction/inference APIs |
| Object storage | Private immutable content, manifests, staged outputs and evidence | Executable/public HTML hosting |
| Publication worker | Commit bounded batches, track publication IDs and reconcile ambiguous outcomes | Independent unsynchronized writes per URL |
| Iceberg/catalog | Versioned analytical schema, snapshots and table/file metadata | Online API admission or job scheduling |
| Trino/BigQuery | Real analytical access and reconciliation | One query per API result lookup |
| Argo | Remote ingest/shard/publish/reconcile DAG with bounded fan-out | A Kubernetes task for every URL or cross-worker origin-rate enforcement |

Actual implementation layout:

```text
crawler-poc\
  Dockerfile
  .specify\
  specs\001-crawler-poc\
  src\crawler_poc\
    api.py  cli.py  config.py  models.py  fetching.py  extraction.py
    storage.py  worker.py  ingestion.py  lakehouse.py  workflow.py
    benchmark.py  evaluation.py  pipeline.py  rendering.py
    ui\index.html  ui\app.css  ui\app.js
  tests\test_*.py  tests\fixtures\
  benchmarks\
  sql\trino\  sql\bigquery\
  deploy\kubernetes\  deploy\argo\
  docs\
```

## 2. Execution profiles

**Core development:** ordinary Python processes, fixture HTTP server, files and SQLite adapter. No local Kubernetes, Docker, Java or Trino installation. SQLite tests are not evidence of remote database concurrency.

**Remote integration:** approved namespace, remote image build/registry, PostgreSQL, private object store, catalog, Trino and Argo. Use namespace-scoped resources only; any missing CRDs/controller setup needs separate administrator approval.

**BigQuery:** real GCP dataset/catalog/connection/IAM and SQL smoke tests, gated on authorization. BigQuery cannot be made local by naming a mock or using DuckDB.

**Public demo:** core API on later-approved Azure/GCP hosting, with private durable backing services and a permitted worker execution model. FastAPI in-process background tasks alone are not a durable queue.

## 3. Proposed API contract

| Operation | Behavior |
|---|---|
| `GET /`, `GET /ui/*` | Public bundled POC workspace/assets; no API key or crawl data embedded |
| `POST /v1/crawls` | Accept one URL or bounded URL list, optional idempotency key and requested top-k; return HTTP 202 and job IDs |
| `GET /v1/crawls/{job_id}` | Return job state, outcome, metadata, topics, versions and provenance |
| `POST /v1/crawls/{job_id}/cancel` | Authenticated cancellation with worker fencing |
| `GET /v1/crawls/{job_id}/content` | Authenticated bounded plain text from this successful job, not the latest URL generation |
| `GET /v1/documents/{url_id}` | Return latest stored metadata/topics without recrawling |
| `GET /v1/documents/{url_id}/content` | Return bounded/paginated plain text, never execute stored HTML |
| `GET /health/live`, `GET /health/ready` | Separate process liveness from backing-service readiness |

The workspace keeps Single URL and Multiple URLs modes. Batches reuse existing
`urls` admission; one row per unique job retains mixed outcomes and exact-job
body/result selection. Automatic batch polling is sequential with 1.5-second
minimum spacing, not a per-URL four-second polling fan-out. Single mode retains
its four-second interval. Cancel applies only to the selected job.

Bulk source ingestion is an authenticated operator CLI/workflow path; do not expose arbitrary MySQL connection strings or unrestricted object URIs to public callers.

Implemented starting configuration: 100 URLs per API submission; top-k default 5
and maximum 10; 5 followed redirect hops; 3 attempts; 5 MiB wire / 10 MiB decoded
document caps (each configurable up to 20 MiB); 512 KiB robots cap;
4 fetch slots per process by default, configurable up to
32; shared one-active-request origin lease in worker CLI. Timeouts, body/read
budgets, backpressure and remaining deployment controls are in `docs\runbook.md`.

Origin includes scheme/host/effective port. Remote aggregate pacing must remain valid across pods and concurrent API/Argo work. Partition ownership or a shared origin-state lease enforces this; per-process semaphores alone do not.

## 4. Fetching, extraction and classification

1. Conservatively normalize URL identity; preserve query semantics, reject credentials and enforce supported schemes/ports.
2. Resolve/validate addresses through the connection path, not just a preflight DNS lookup. Retain the requested host for TLS verification/SNI.
3. Fetch/cache robots under its own bounds and policy; use a declared crawler user agent.
4. Stream bounded HTTP content with connection pooling. Guard every redirect and robots redirect; do not inherit ambient proxies or client credentials.
5. Distinguish invalid, forbidden, robots-disallowed, target-blocked, unavailable, retry-exhausted, non-HTML, too-large, insufficient-content and success outcomes.
6. Extract title/description/headings/canonical candidate, Open Graph/Twitter fields and bounded JSON-LD without following remote contexts or executing scripts.
7. Extract clean body text separately; make precision/recall fallback explicit and test product/article/category cases.
8. Classify page type from schema/content evidence. Use local YAKE-style keyphrases with metadata weighting, normalization/deduplication and evidence. Return unknown/empty with reason when evidence is insufficient.

The v2 refinement preserves non-article repeated records through a bounded,
reported visible-text fallback when precision extraction severely under-retains
the selected content region. Microdata and identifier-plus-price fact tables
provide generic product evidence; main/article headings and sentence-separated
topic inputs reduce dialog and cross-boundary noise. This changes neither URL
discovery scope nor network/access policy. Selected live coverage and same-HTML
completeness tests supplement, but do not replace, an independent quality study.

The user-requested v3 delta adds bounded rich metadata, homepage evidence,
location-weighted/diversified topics and measured pipeline timings. Optional
Playwright executes only permitted successful JS shells; every resource is
fulfilled through the existing guarded Python fetcher, never raw browser egress.
See `docs\architecture-alignment.md` for request/byte/time/feature boundaries,
storage mappings, explicit unsupported browser cases and the Cloud Run API versus
worker lifecycle decision. No provider, public endpoint or image build is approved.

Robots policy proposal: honor RFC rule matching and caching; treat unavailable network/5xx robots conservatively, handle missing robots according to a documented standard-aware rule, and never retry indefinitely. An HTTP challenge/login page must not become a successful content classification.

## 5. Ingestion, scheduling and recovery

- Text sources are streamed line-by-line; MySQL uses read-only, parameterized keyset pagination or a verified streaming cursor, with explicit high-watermark/source-snapshot behavior.
- Validate the year-month and source timezone semantics. Preserve input order/row identity for accounting, not necessarily execution order.
- The POC consumes already bounded file/GCS shards and persists disk-backed aliases.
  Production bounded manifest generation/origin-fair assignment remains design
  work; do not claim the sequential shard DAG ingests billions at once.
- Use at-least-once claims, leases, heartbeats and fencing tokens. Do not hold database transactions open during HTTP requests.
- Retry transient target/network failures with capped backoff/jitter and Retry-After handling; do not retry permanent/policy failures as transient outages.
- Store aliases, terminal result and attempt count with fenced jobs and a
  transactional outbox. A full historical attempt log remains production work.
- Backpressure must limit accepted/claimed work when parsing, storage or publication falls behind.
- For the production design, compare a durable partitioned queue/frontier and provider-native key/value serving store. A PostgreSQL queue is a POC choice, not a billion-job scaling assertion.

## 6. Storage/catalog and consistency

- Private content-addressed compressed objects for raw/clean bodies; columnar analytical metadata contains bounded previews/references rather than duplicating unbounded content.
- Proposed Iceberg `crawler.crawl_events`, append-oriented logical terminal events, v2/Parquet, explicit schema IDs/versions.
- Partition by observed UTC day. An additional bounded bucket transform is
  deferred until distribution/query measurement; no per-URL/domain partitions.
- Use batches large enough to avoid per-URL files/commits while respecting bounded memory. Tune file sizing from measured record sizes, not a hardcoded giant target.
- Table publication/maintenance has one ownership domain in the POC. An ambiguous post-commit crash is resolved using the publication ID and committed snapshot/table state before retrying.
- Compaction, snapshot expiration and orphan cleanup require reference/retention safeguards. No broad deletion based only on object age.
- Rebuild latest-result projections from durable events/outbox. Track projection lag and analytical publication lag separately.

### BigQuery topology decision

Preferred candidate: externally owned Iceberg with compatible REST catalog, Trino reader and read-only BigQuery access. GCS/Google Lakehouse catalog is the most direct GCP-aligned candidate, not a provider decision.

Alternative: explicit snapshot-metadata external registration with controlled refresh; document that it is not Google's general default recommendation. Another alternative is a BigQuery materialized projection with a declared watermark and extra storage/cost. Either deviation needs a decision-log update and owner approval.

BigQuery-managed Iceberg is a different ownership model: BigQuery must own the write path. Do not point PyIceberg/Trino writers at those managed files. Azure app hosting does not eliminate the GCP requirement or cross-cloud egress/identity concerns.

## 7. Argo workflow

```text
validate-source -> emit-bounded-manifests -> execute-shard-workers
                                         -> publish-batches
                                         -> reconcile
                                         -> publish-evidence/report
```

Use bounded child workflows/pages of manifests or a fixed worker pool consuming durable shard references. Do not expand an unbounded `withParam` array into workflow state. Persist checkpoints/artifacts outside pods.

Set explicit parallelism, resource quotas, retry policy, completion/cleanup policy, service account and cancellation behavior. Choose fail-fast versus finish-independent-shards deliberately. Argo retries must re-enter the application's idempotent protocol, not blindly re-append data.

## 8. Scale and cost model

Define variables before quoting capacity:

- Input URLs, duplicate/invalid rates, distinct origins and hot-origin skew.
- Fetchable/blocked/failed proportions, retry amplification and allowed origin rates.
- Wire/decoded/raw-compressed/body/metadata sizes and their distributions.
- Parse/classify CPU, active memory per document, worker utilization and network limits.
- File sizes/counts, manifests, snapshot growth and compaction overhead.
- Peak read RPS, cache hit rate, result sizes, freshness and tenant/domain skew.

Model relationships:

```text
unique_work = valid_input - duplicate_aliases
attempts = unique_work * measured_attempt_amplification
required_fetch_rate = unique_work / agreed_processing_window_seconds
network_bytes = attempts * measured_wire_bytes
stored_bytes = retained_versions * unique_work * measured_stored_bytes
worker_capacity = min(network, CPU, memory, storage, allowed_origin_budget)
serving_database_reads = peak_read_RPS * (1 - cache_hit_fraction)
query_scan_bytes = bytes_selected_after_partition_and_column_pruning
```

Do not linearly extrapolate a same-host local mock benchmark to billions of public URLs. Hot domains can cap throughput regardless of worker count.

Final cost worksheet separates worker compute, egress, storage operations/retention, PostgreSQL or key/value serving, catalog/Trino/Argo infrastructure, BigQuery scan/compute and observability. Compare Azure-first/GCP-aligned topologies after region and authorization are selected; do not fabricate a monthly bill now.

## 9. POC evaluation, SLOs and operations

Test metadata field accuracy, page-type macro-F1, topic precision@k/nDCG, abstention and failure categories on a small diverse manually reviewed set. Record annotations/provenance and avoid overfitting to the three sample URLs.

Benchmark parse-only, controlled-network, source/persistence/publication, and serving paths separately. Use 10k then 100k controlled records; report counts, payload distributions, versions, warm/cold cache state, CPU/RSS, latencies, throughput and errors. The model comparison is opt-in and does not change baseline behavior without evidence.

Proposed design targets: eligible API availability 99.9%; controlled warm result lookup p95 250 ms. Queue freshness and analytical lag targets remain workload/owner decisions. No contractual SLA or availability measurement is claimed.

Monitor admissions, terminal outcome counts, queue age, origin wait/backoff, fetch/parse latency, resource saturation, dead letters, lease expiry, publication/projection lag, Iceberg file/manifest counts, commit failures, analytical scan bytes, read latency and cost. Avoid URL/domain labels with unbounded cardinality. Alert on error-budget burn, stalled progress and failed reconciliation.

## 10. POC-to-release gates

| Gate | Required evidence |
|---|---|
| G0: ready to code | Ratified scope/constitution, actual Spec Kit analysis, resolved critical/high findings |
| G1: core POC | Real safe fetch/extract/classify/API with deterministic tests and durable recovery |
| G2: data POC | Real remote Iceberg/Trino/Argo run, replay and reconciliation |
| G3: BigQuery | Real GCP query of a declared publication/projection with cross-engine reconciliation |
| G4: quality/performance | Reproducible correctness/quality/resource measurements and limitations |
| G5: public demo | Authorized Azure/GCP endpoint, authentication/limits and external smoke test |
| G6: submission | Parts 1/2/3 docs, final scheduling/estimation artifact, AI/license disclosure, rollback/teardown and clean bundle |

Roll out schema-compatible changes before new writers; use a limited fixture/small approved URL canary before wider input. Roll back application/image versions without deleting committed analytical history. Stop admission/worker claims on an incident; retain leases/checkpoints/evidence for reconciliation.

Scheduling/estimation deliverable for Part 3 remains required: separate known implementation work from compatibility/authorization experiments, state dependencies and estimate assumptions after validation, and document uncertainty. No numerical delivery dates or durations are proposed here.
