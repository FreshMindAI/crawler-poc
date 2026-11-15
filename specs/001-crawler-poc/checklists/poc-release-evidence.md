# POC-to-release evidence checklist

Kind: project-specific acceptance/evidence checklist, not a reusable Python/Argo/Iceberg technology standard. Authority: `spec.md` requirements and the draft constitution. All boxes are intentionally unchecked; a reviewer records the concrete evidence before making an assertion.

## Foundation and core POC

- [ ] POC-001: Approved scope/constitution and actual compatible Spec Kit clarify/checklist/analyze evidence exist. [T01; constitution IX]
- [ ] POC-002: Dependencies and outbound services show no managed crawler/extractor/classifier substitution. [FR-025, FR-027; T20]
- [ ] POC-003: Submit/poll/latest/content works with real submitted code and bounded safe output. [FR-001, FR-005, FR-013; T05]
- [ ] POC-004: Forbidden DNS/redirect/robots destinations receive zero requests in safety tests. [FR-002, FR-003; T03]
- [ ] POC-005: Retry, redirect, response/decompression, concurrency and cancellation budgets have passing edge-case tests. [FR-004, FR-009; T03, T05]
- [ ] POC-006: Product/article/category/sparse fixtures have metadata/page-type/topic quality evidence, including honest unknown outcomes. [FR-005 through FR-008; T04]
- [ ] POC-007: Original assignment URLs have recorded live outcomes; dead/blocked pages are not quietly replaced or bypassed. [AC-003, Q-009; T19]
- [ ] POC-008: Duplicate input, conflicting idempotency keys, expired leases and stale workers preserve effective-result identity. [FR-009, FR-010; T05, T07]
- [ ] POC-009: Text/MySQL source resumes, month filtering and invalid/duplicate accounting reconcile. [FR-011; T06]
- [ ] POC-010: Private content storage, log redaction and bounded text serving are verified. [FR-014; T07, T20]

## Remote data POC

- [ ] POC-011: Remote namespace/build/registry/data permissions and spending boundaries are explicit; no local infrastructure was installed. [D-006, D-007; T08, T09]
- [ ] POC-012: A real Python-written cataloged Iceberg v2/Parquet table is queried by real Trino. [FR-015, FR-016; T10, T11]
- [ ] POC-013: Batch/publication replay survives crash after commit before acknowledgment without duplicate effective events. [FR-019; T11, T15]
- [ ] POC-014: Argo actually executes bounded shard references, retries/cancellation and durable reconciliation. [FR-017; T12, T15]
- [ ] POC-015: Global origin pacing remains correct across worker replicas, not just inside one process. [FR-003, FR-004; T12, T15]
- [ ] POC-016: Real BigQuery query evidence reconciles the declared publication/snapshot or projection watermark with Trino. [FR-018, FR-019; T14]
- [ ] POC-017: Catalog/auth renewal, nested/null/timestamp mappings and maintenance ownership pass the compatibility record. [FR-012, FR-015; T10, T14]

## Evaluation and release

- [ ] POC-018: Controlled 10k/100k inputs have raw throughput/latency/CPU/RSS/error evidence and declared fixture distributions. [FR-021; T16]
- [ ] POC-019: Topic/page-type quality labels, baseline results and pretrained backup/comparison plan are retained. [FR-021, FR-026; T17]
- [ ] POC-020: Billion-URL and large-read design covers host skew, source dedup, queue/serving partitions, storage/compaction and realistic bottlenecks. [FR-022; T19]
- [ ] POC-021: Cost assumptions, pricing sources, regional/cross-cloud effects and query-scan budgets are disclosed. [FR-022, NFR-007; T19]
- [ ] POC-022: SLO/SLI definitions, alerting, failure drills and SLA limitations are documented without unsupported guarantees. [FR-023; T15, T19]
- [ ] POC-023: Public Azure/GCP HTTPS endpoint passes genuine external authenticated submit/poll/read and abuse-limit smoke tests. [FR-020; T18]
- [ ] POC-024: Final Part 3 blockers, engineering breakdown, scheduling/estimation assumptions, release, rollback and teardown documentation are present. [FR-024; T19]
- [ ] POC-025: Formatting/lint/types/tests, SQL/YAML validation and image/dependency/secret checks pass against pinned versions. [FR-025, NFR-008; T20]
- [ ] POC-026: Clean submission includes quickstart, evidence references, limitations, AI assistance, licenses and allowed delivery format. [FR-025; T20]

Core POC completion is not final assignment completion. POC-016 and POC-023 remain mandatory even when cloud access/hosting is deferred.

Reusable implementation standards, if installed later, retain their original IDs/provenance and are not silently overwritten or checked by the assistant. Tailor technology copies with documented reasons; missing dedicated standards follow the review kit's Route C process.
