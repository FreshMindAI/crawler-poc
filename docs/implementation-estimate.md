# Conditional engineering estimate (assignment Part 3)

These are rough-order-of-magnitude **remaining engineering effort** estimates,
not elapsed calendar promises, measured time spent, or a proposed evaluator
deadline. They assume one engineer familiar with Python/Kubernetes, prompt owner
decisions, existing supported remote services/CRDs and no procurement/platform
build. Authorization wait time is excluded and can dominate elapsed delivery.

| Remaining package | Focused engineer-days, indicative | Dependency / uncertainty |
|---|---:|---|
| Remote identity/build/deployment/egress profile | 2-4 | Authorized inventory, service owners and quotas |
| Catalog/Trino/BigQuery compatibility and integration evidence | 3-7 | Supported ownership topology; largest experiment risk |
| Remote replay/fault drills, monitoring and recovery | 2-4 | Working data-stack spike and bounded Argo execution |
| Held-out human quality review and realistic performance evaluation | 2-3 | Reviewer labels/workload targets; model comparison optional |
| Public canary, abuse/TLS/backup controls and external validation | 2-4 | Approved provider/region/budget and platform access |
| Final evidence, dependency/image review and submission packaging | 1-2 | All mandatory integration/demo gates passed |
| **Total engineering effort under those assumptions** | **12-24** | Not a calendar commitment; dependencies are not all parallel |

Local core implementation/specifications/tests already exist; no retrospective
effort or AI time-saving number is invented. A new Azure Blob adapter, unsupported
catalog authentication, unavailable existing infrastructure, a required trained
taxonomy/multilingual renderer, or a production billion-URL system changes this
estimate and needs a new scope/decision record.

Scheduling order is authorization -> compatibility spike -> bounded integrated
POC/fault evidence -> public canary -> release. Human corpus work and design/cost
review can proceed independently once workload assumptions are agreed. Re-estimate
after the compatibility spike with observed task effort; do not silently consume
the upper range while leaving mandatory evidence unperformed.

## Weekly Release Cadence Plan (BrightEdge Agile Delivery)

To fit BrightEdge's **weekly release cycle**, the remaining POC-to-production roadmap is broken into **4 weekly shippable increments (W1–W4)**, each with an independent release gate, feature flag (`CRAWLER_*`), and zero-downtime rollback boundary:

| Weekly Release | Shipped Increment | Weekly Release Gate & Verification | Rollback Mechanism |
|---|---|---|---|
| **Week 1 (v0.1 — Core & Cloud Canary)** | Deploy stateless FastAPI + HTTP/Playwright crawler image to Cloud Run / Container Apps with managed PostgreSQL & private GCS; ship Part 1 API (`/v1/crawls`, `/v1/documents/{url_id}`). | 91 unit/browser tests pass; external HTTPS smoke test on the 6 assignment/homepage URLs; p95 warm metadata read < 250 ms; `CRAWLER_BROWSER_FALLBACK` toggleable via env. | Pin previous container digest; disable `CRAWLER_BROWSER_FALLBACK=false` if browser memory spikes. |
| **Week 2 (v0.2 — Lakehouse & Catalog Spike)** | Enable transactional outbox -> Apache Iceberg v2 (`crawler.crawl_events`) daily-partitioned commits on GCS/REST catalog; connect Trino and BigQuery external tables. | `crawler publish` + `crawler trino-report` and `crawler bigquery-report` reconcile 100% of batch row counts and snapshot IDs on 10k-row test batch. | Outbox retains unpublished events in PostgreSQL; Iceberg snapshot rollback via `publish_batch_id` predicate overwrite. |
| **Week 3 (v0.3 — Bounded Argo Batch & Replay)** | Release Argo Workflows DAG (`deploy/argo-workflow.yaml`) for monthly text/MySQL ingestion (`ingest`, `ingest-mysql`), bounded 4-worker shard pool, and automatic reconciliation. | 100k-record streamed ingestion benchmark (`1,267 rec/s`), crash-before-ack replay drill, and zero duplicate `event_id` rows verified in Trino/BigQuery. | Suspend Argo CronWorkflow/trigger; drain active leases; resume from high-watermark `run_id`. |
| **Week 4 (v1.0 — Production SLOs, Evaluation & Hardening)** | Ship held-out human relevance evaluation (`evaluate`), domain-fair frontier scheduling, Prometheus/Cloud Monitoring alerts, and production cost/scan guardrails. | Macro-F1 / precision@k sign-off on held-out corpus; 99.9% API availability SLO alert rules active; security/license/SBOM sign-off (`dependencies.json`). | Revert extractor/classifier version (`v3` -> `v2`) via `generation` tag without mutating historical Iceberg partitions. |
