# Engineering tasks

This is the engineering dependency/evidence specification, manually reconciled
with pinned Spec Kit procedures. It is not automatically generated command output.
The implementation snapshot below distinguishes verified local work from blocked
remote evidence; session SQL also tracks status.

Paths now refer to the project. Original remote prerequisites remain genuine
execution gates; authoring a template/client is not a passed integration task.

| ID | Deliverable / intended files | Dependencies | Requirements | Verification / exit evidence |
|---|---|---|---|---|
| T01 | Create project; pin toolchain and compatible Spec Kit; reconcile `.specify\memory\constitution.md`, `specs\001-crawler-poc\*`; establish `pyproject.toml`/lock and CI choices | Plan approval | FR-025; all spec gates | Version/interface record, genuine clarify/checklist/analyze results; no high/critical unaccepted findings |
| T02 | Define API/data/config contracts and diverse hand-authored fixtures under `tests\fixtures`; record source/quality labels | T01 | FR-001, FR-005 through FR-008, FR-012 | Contract fixtures include success, missing/null, Unicode, malformed, blocked and unsupported cases |
| T03 | Build `fetching`/`scheduling`: guarded resolution/connect/redirects, robots, finite budgets, pacing and retry classification | T02 | FR-002 through FR-004, FR-008, FR-027 | Focused safe-network/mock tests with zero forbidden requests |
| T04 | Build `extraction`/`classification`: metadata/body, page-type rules and local topic ranking/versioning | T02 | FR-005 through FR-008, FR-027 | Labeled product/article/category/sparse-page tests and baseline quality report |
| T05 | Build `api` and operational adapters: submit/poll/latest/content, authentication/limits, idempotency, job leases and latest projection | T03, T04 | FR-001, FR-009, FR-010, FR-013, FR-014 | API contract tests, duplicate/concurrency/stale-worker/restart cases |
| T06 | Build `ingestion`: streaming text/MySQL adapter, read-only keyset/checkpoint behavior and bounded manifests | T02 | FR-010, FR-011 | Resume/invalid/duplicate/month-boundary tests and complete source accounting |
| T07 | Build `storage`/publication staging: private objects, hashes, transactional outbox and bounded deterministic publish batches | T05, T06 | FR-012, FR-014, FR-019 | Crash/replay cases, valid object refs, bounded memory and deterministic batch identity |
| T08 | Obtain authorized remote namespace/endpoints, image build/registry, resource limits, credentials mechanism and permitted operations | Owner authorization | FR-015 through FR-017 | Written non-secret environment inventory and explicit permissions; no cluster-wide assumptions |
| T09 | Add remote image-build definitions and `deploy\kubernetes` profiles with probes, quotas and least-privilege service accounts | T01, T08 | FR-009, FR-014, FR-025 | Reproducible remote image build and namespace-scoped validation/smoke test |
| T10 | Run tiny real catalog/auth/version spike; record compatibility decision in `spec.md` and `research.md` | T02, T09 | FR-012, FR-015, FR-016 | Python writes Iceberg; Trino reads; schema/token-refresh/second-commit evidence; decide supported catalog |
| T11 | Add `lakehouse` writer/recovery and `sql\trino` reconciliation/pruning queries | T07, T10 | FR-015, FR-016, FR-019 | Real committed batches; crash-after-commit replay without duplicates; query plans/counts |
| T12 | Add `deploy\argo` bounded ingest/shard/publish/reconcile/report workflow | T09, T11 | FR-017, FR-019 | Real remote Argo run, bounded workflow state, cancellation/retry/checkpoint evidence |
| T13 | Agree authorized GCP project, dataset/catalog/storage location, IAM, billing limits and cleanup ownership | Later cloud approval | FR-018 | Non-secret resource/authorization record; no cloud actions before approval |
| T14 | Add real BigQuery integration, `sql\bigquery` and opt-in cloud tests; document catalog or projection/watermark model | T10, T11, T13 | FR-018, FR-019 | Actual query/job evidence; Trino/BigQuery counts and normalized sample aggregates reconcile |
| T15 | Add metrics/tracing/structured-safe logs, alerts/runbook and remote failure drills | T12 | FR-009, FR-019, FR-023 | Interrupted workflow/lease/publication recovery, stall/reconciliation signals and retained evidence |
| T16 | Add controlled `benchmarks` and evaluation report: parse/fetch/storage/API paths, 10k and 100k records | T07 | FR-021, FR-022 | Raw measured outputs, quality labels, environment/versions, CPU/RSS and bottleneck analysis |
| T17 | Write local pretrained NLP backup study; implement opt-in local inference benchmark only if approved/feasible | T04, T16 | FR-026 | Same-corpus comparison plan; model/license/revision/resource record; no forced baseline change |
| T18 | Choose approved Azure/GCP public hosting; deploy API/worker with durable state and demonstrate external requests | T05, T08, T16, hosting approval | FR-020 | Reachable HTTPS endpoint, authenticated submit/poll/read and abuse/safety smoke tests |
| T19 | Write `docs\scale-design.md`, `docs\poc-evaluation.md`, `docs\release-plan.md`, `docs\ai-usage.md`, quickstart and submission manifest | T10, T16, T17 | FR-022 through FR-026 | All assignment parts mapped; final scheduling/estimation deliverable and limitations present |
| T20 | Final checks across code, images, SQL/YAML, remote stack, BigQuery, public demo and submission bundle | T12, T14, T15, T18, T19 | FR-001 through FR-027 | Formatter/lint/types/tests, genuine integration evidence, reviewer-owned release gate and clean deliverable |

## Dependency notes

- T03 and T04 are independent implementation streams; T06 can also proceed after T02.
- T08/T13 require explicit resource authorization; neither is an instruction to discover credentials.
- T10 is an early risk-reduction experiment, not a document-only connector configuration.
- T14 is blocked without GCP access. T18 is blocked without hosting approval. Their status cannot be waived by using a mock.
- T16 covers core controlled performance; remote/analytical failure and reconciliation evidence additionally comes from T11/T12/T14/T15.
- T17 requires a documented backup and benchmark plan; actually downloading/running a pretrained model is optional and separately gated.
- T19 may be drafted earlier, but its final evidence must match the implemented system. T20 remains blocked until all mandatory public/remote/cloud evidence exists.

## Known versus uncertain work

Known engineering patterns: schema/API contracts, parser integration, deterministic fixtures, bounded readers, authentication/limits and telemetry.

Experiments/risks: sample-page accessibility, body extraction quality outside articles, topic relevance expectations, distributed origin fairness, catalog/token/version interoperability, post-commit replay, remote quotas/egress and real cloud economics.

Part 3's final schedule/effort-estimation document must distinguish these categories and state assumptions/dependencies. This task plan intentionally contains no numerical duration/date estimates.

## Implementation snapshot

| Tasks | Local outcome | Remaining gate |
|---|---|---|
| T01 | Git/project, isolated pinned packages, official source templates/scripts, actual prerequisite check, manual analysis/clarification record | Modern CLI lifecycle did not execute; initial analysis ordering deviation retained |
| T02-T05,T07 | Contracts, fixture extraction, guarded fetch, durable authenticated API, content/outbox/replay tests pass | Production network/IAM/realistic quality/availability evidence not inferred |
| T06 | File streaming/resume/accounting/100k benchmark; MySQL/GCS adapters implemented | Real MySQL/GCS source/index/identity/snapshot verification |
| T08,T13,T18 | No unauthorized action attempted | Owner resource/cloud/hosting authorization and actual public endpoint |
| T09 | Docker/Kubernetes profiles authored, YAML parsed | Remote image build, immutable digest, installed-schema/identity/egress validation |
| T10 | Local real Iceberg is not substituted for the spike | Real remote catalog/Python/Trino/BigQuery interoperability |
| T11 | Real local v2/day-partitioned publication and post-commit replay; Trino client/SQL | Actual Trino counts/normalized values/pruning |
| T12 | Bounded fixed-pool DAG/RBAC and command contracts authored | Real Argo execution, cancellation, controller/version/permission validation |
| T14 | Real BigQuery SDK query/cost cap and opt-in test authored | Authorized GCP access and actual query/publication evidence |
| T15 | Basic metrics/readiness, leases/fencing/concurrency and local replay tests; runbook | Remote fault drills, tracing/timing histograms, alerts/backup/restore |
| T16 | Actual 10k/100k stage and tiny synthetic quality evidence | Human held-out relevance study and sustained realistic remote workload |
| T17 | Local pretrained backup/license/revision/comparison procedure documented | Optional model download/inference intentionally not performed |
| T19 | Quickstart, scale/POC/release/estimate/AI/submission docs assembled | Replace all remaining cloud evidence gaps before final submission |
| T20 | Local tests/format/lint/types/artifact checks | Remote/public/integration, image/security/license review and human release assertions |

This table does not tick or supersede reviewer-owned checklists.

## Original-URL failure-fix follow-up

T03/T04/T05/T07 were refined under the user's "fix these" request:
separate wire/decoded budgets, head-only document title, contextual typed errors,
cached robots-denial provenance, bounded HTTP-date retries and status-first error
handling. Decisions D-037 through D-040 and research R-019 capture rationale.
Fourteen additional regression cases bring the suite to 66 passed / one remote
skip; formatter/lint/types/dependency checks pass.

A fresh authenticated real TCP API/worker run extracted the original CNN URL,
verified latest metadata and bounded body reads, and published all three outcomes
to real local Iceberg with matching status/error metadata. The unchanged Amazon
URL still returned 503 on three attempts; REI robots still returned 403 and its
article was not fetched. These upstream access/availability blockers are not
silently treated as repaired. Evidence:
`docs\evidence\url-fix-20261114T094736Z-415670.json`.

## Real-site readiness correction

The user's challenge prompted a wider, bounded static-HTML check rather than
treating typed failure handling as a complete crawler. Eight of eleven selected
live URLs fetched/extracted/stored content, but quality inspection found missing
structured records, product misclassification and topic boilerplate. T04 was
refined with domain-independent content/evidence rules, a reported bounded
fallback, sentence boundaries and versioned v2 results (D-041 through D-043,
R-020). No network policy was loosened.

All eight fetched raw pages were compared offline using identical saved HTML.
Explicit checks cover product type, all 250 country names and the observed CNN
dialog/cross-boundary noise. Four new regressions bring the suite to 70 passing
tests / one cloud skip. These checks are not a human relevance/generalization
study; T16's independent quality gate and all remote/public gates remain open.
Current extraction speed was remeasured, not assumed unchanged: 131 records/s
on the repeated 10k synthetic template in this shared-machine run.

## User architecture refinement

D-044 through D-050 / R-021 through R-024 refine existing T03/T04/T05/T07/T15/T16:
reusable analysis pipeline, opt-in guarded JS-shell execution, richer bounded
metadata, homepage evidence, metadata-weighted/non-contained topics and actual
timings. Existing async API, control durability, libraries and physical Iceberg
schema are retained. The implementation ledger and deliberate deviations are in
`docs\architecture-alignment.md`; no task dependencies or human checkbox states
were changed.

Final local result: 89 passing tests / one cloud skip, with actual installed
headless-browser tests enabled; lint/format/types/dependencies pass. The expanded
six-input run fetched three pages, retained three explicit failures, verified
API/body reads and all six new-detail/status rows in local Iceberg. Same-HTML
topic cleanup needs no repeat public requests. The optional browser image is
only authored; v3 performance, independent semantic relevance, remote mandatory
engines, image/sandbox/security review and public deployment remain release gates.
