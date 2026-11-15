# Unified data model and consistency contract

Status: implemented local POC mapping; remote interoperability is unverified.
The production extensions below are explicitly not deployed entities.

## Versioned record mapping

| Logical field | API/operational representation | Iceberg representation |
|---|---|---|
| Schema | `schema_version=1` | integer |
| Identities | SHA-256 `event_id`, `job_id`, `url_id`; `normalized_url`, `generation` | strings with the same names |
| Source | `run_id`, `source_month`; row/line aliases in `input_records` | nullable strings; lineage remains in SQL |
| Time | `created_at`/`updated_at` on job; `observed_at` UTC Unix seconds in result | `observed_at` microsecond UTC timestamp |
| Lifecycle/outcome | job `status`; result `outcome`, nullable `reason` | outcome/reason; no duplicate lifecycle status column |
| Attempts | job `attempts`, result `attempt_count` | integer; no separate deployed attempt-history table |
| HTTP | `http_status`, `final_url`, `content_type` when known | nullable integer/string fields |
| Metadata | title, description, canonical_candidate, language, headings | nullable strings/list of strings |
| Structured/social/extraction evidence | selected `metadata` map including `body_extraction`, `content_scope`, optional `product_evidence`; `structured_types` | existing `metadata_json` string and list of strings |
| Failure context | `metadata.failure_stage`, redacted `failure_url`, optional string `failure_limit_bytes`/`failure_observed_bytes` | preserved in existing `metadata_json`; no new physical columns |
| Classification | page_type, classifier_version, topics | string versions/type; list of phrase/rank/raw_score/method/evidence structs |
| Content | raw_ref/body_ref are SHA-256 content hashes; body_preview, body_characters, raw_bytes | same names; bounded preview and object references, not unbounded full body |
| Provenance | normalization_version, fetcher_version, extractor_version, warnings | same strings/list; versions separate from format version |
| Publication | SQL outbox `batch_id` and batch ledger | `publish_batch_id`; snapshot/metadata reference in acknowledgment |

Failure fields can be null. Failures do not fabricate titles/topics/body. Observed
HTTP status/content type and safe failure-stage/URL/limit context survive terminal
worker/API/outbox publication. Page `final_url` is known only after a page response;
robots-only failures keep it null even when their HTTP status is known. Diagnostic
failure URLs omit queries/fragments; normal page final URLs preserve input
semantics. Complete per-attempt HTTP/timing history is future work.
Language is declared HTML/metadata evidence, not model detection.
Canonical tags remain untrusted candidates and never rewrite identity.

New extraction results use `html-trafilatura-v3` /
`schema-rules-yake-weighted-v3`.
Previously stored results retain their original versions. The logical schema
remains version 1: strategy evidence fits the existing string map and a new
generation requests explicit reprocessing rather than rewriting history.

Additive operational fields include bounded `json_ld`, `keywords`, `breadcrumbs`,
`image_alt`, `links`, internal/external link counts, author/publication-time
candidates, word count, page-type evidence, `fetch_method`, `timings_ms` and topic
`ranking_score`. `metadata.extracted_details_json` preserves all these new
extraction details and complete topics, including weighted scores, in Iceberg's
existing string map. The original physical topic struct still has
phrase/rank/raw_score/method/evidence; it must not be mistaken for an added
physical weighted-score column. Timings and fetch method are also in metadata.

For rendered success, `raw_ref` is a bounded rendered DOM snapshot,
`metadata.raw_representation=rendered-dom`, and `initial_raw_ref` references the
original static HTML object. A rendering failure may retain actually observed
`partial_title`/`partial_description` and `initial_http_status` in error metadata;
these do not fabricate body/topics or overwrite the failing resource's status.

The local Arrow-to-Iceberg schema is in `lakehouse.arrow_schema`; successful
results are extended with stable fields by `Store.finish`. Selected metadata is
JSON-serialized explicitly rather than silently discarded. Observed-day
partitioning is real; additional bucketing remains an experiment.

## Operational entities actually created

| Table | Grain/key and invariant |
|---|---|
| `crawl_runs` | run ID -> immutable input fingerprint, month and optional MySQL high watermark |
| `input_records` | `(run_id, offset)` -> job ID or rejection; admitted/duplicate/rejected; indexed run/job alias lookup |
| `crawl_jobs` | job ID -> normalized URL/generation/top-k/source context, status, token, attempts, availability/lease, result |
| `idempotency_keys` | principal-scoped hashed key -> payload hash and stable response |
| `origin_state` | origin -> owner, lease expiry and next allowed request time; robots cache is per-process bounded memory |
| `documents_latest` | URL ID -> latest successful generation by job creation time; stale finishes are fenced |
| `result_outbox` | one publishable terminal event -> immutable payload, batch identity, published flag |
| `publish_batches` | deterministic batch ID -> pending/published, row count and acknowledged containing snapshot ID |
| `api_budgets` | minute bucket -> shared authenticated request count |

SQLite/files are development adapters. Remote PostgreSQL/GCS need real
concurrency/identity/failure validation. `metadata.create_all` initializes a new
schema; it is not an upgrade migration system.

## Identity, lifecycle and recovery

- Normalize scheme/host/default port/fragment conservatively; preserve query
  ordering/repeats and path case. Job identity hashes principal + URL + explicit
  generation + top-k. API/batch principals differ.
- Idempotency-key payload mismatch yields conflict. Cryptographic SHA-256
  collisions are assumed negligible, not separately detected for every object/
  URL identity. Objects are verified by hash when read.
- `queued -> running -> terminal`; delayed retry returns to queued. Reclaim
  expired running leases with a higher token. Heartbeats extend active jobs;
  canceled/stale tokens cannot finish into projections/outbox.
- Write immutable objects before the SQL terminal transaction; job, latest
  success and outbox commit atomically. An interrupted write can leave an
  unreferenced object, never permission to broadly delete objects by age.
- Cancellations retain terminal operational outcome but are deliberately not
  analytically published. Other worker terminal outcomes are publishable.
- Single-owner publication prepares deterministic batches, scans matching
  publication IDs and checks the full event-ID set. Predicate overwrite commits
  one logical batch; a commit-before-ack replay verifies it instead of appending
  duplicates. The local real replay test covers this boundary.
- Acknowledgment records a snapshot containing the recovered batch, not a
  distributed transaction across SQL and Iceberg. Remote catalog conflicts,
  maintenance, retention and cross-controller ownership still need proof.

## Accounting and retention

```text
input_rows = rejected + admitted + duplicate_aliases
admitted = unique jobs within the run
unique jobs = nonterminal + terminal
publishable terminal = terminal - canceled
published events <= publishable terminal
admission budget = nonterminal jobs + unpublished events
```

Final source/run, object-reference and cross-engine reconciliation are separate
from the CLI's operational queue/outbox drain check. Compare BigQuery/Trino for
the same declared batch/snapshot visibility, never unrelated moving latest states.

No automatic destructive retention/deletion job is enabled. Production must
define raw/clean/analytical/backup retention and deletion across objects,
projections, snapshots and backups. Additional attempt history, manifest/shard
scheduler, distributed frontier/cache and projection rebuild tools are production
extensions, not misleadingly listed as implemented POC tables.
