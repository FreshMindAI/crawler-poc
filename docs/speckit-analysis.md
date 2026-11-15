# Spec Kit semantic analysis and process evidence

## Execution provenance

This is a **manual agent execution of the pinned Spec Kit analysis procedure**,
with input artifacts read non-destructively and this report captured separately.
It is not automatic CLI/slash-command output, SDD adoption scoring, or a claim
that a complete modern Spec Kit lifecycle ran.

Official templates/scripts are vendored at source revision
`2ee2b1e8005905db05f5717300a469b3068b908f`; analysis method:
`.specify\templates\commands\analyze.md`. Existing global Specify 0.0.22 could not
consume current release assets; isolated 1.4.0 download failed TLS. The fallback
and unchanged global installation are recorded in `.specify\bootstrap.json`.

The actual prerequisite script was executed from project root with
`SPECIFY_FEATURE_DIRECTORY=specs\001-crawler-poc`,
`-Json -RequireSpec -RequireTasks -IncludeTasks`. It found the required spec,
plan/tasks and research/data-model documents. `.specify\extensions.yml` is absent;
there were no extension hooks to invoke.

Inputs analyzed: current constitution 0.2.0; specification FR/NFR/AC/decision/
question inventories; architecture/constraints; all 20 tasks/prerequisites;
physical model; original source research and implementation evidence.
Passes covered duplication, ambiguity, underspecification, constitution
alignment, planned requirement coverage and cross-artifact inconsistency.

**Process deviation:** initial implementation started before a retained
post-bootstrap semantic-analysis report. This cannot be repaired retroactively by
calling a prerequisite check “analysis.” The compensating full pass and
constitution amendment are explicit; human process/release review remains open.
Drafting/clarification/planning/tasks were manual, not claimed CLI generation.

## Findings and disposition

| ID | Severity/category | Location | Finding and disposition |
|---|---|---|---|
| SK-001 | Resolved / missing foundation | `.specify`, `pyproject.toml` | Initial absent project is now a real Git project with pinned framework source, isolated dependencies, source/tests/CLI. |
| SK-002 | High / process | constitution IX; spec D-027 | Full modern CLI lifecycle did not execute and initial ordering deviated. Retain fallback/manual evidence; do not claim clean automatic lifecycle or independent human ratification. |
| SK-003 | High / stage gate | spec Q-001/Q-002; tasks T08/T13/T18 | No authorized remote/public environment. **Blocks integration/deployment/release**, not local tests. |
| SK-004 | High / interoperability | plan section 6; tasks T10/T14 | Python/REST/stock Trino/BigQuery auth/visibility not proven; real compatibility spike remains mandatory. |
| SK-005 | High / ownership risk | spec D-015/D-031/D-034 | BigQuery-managed versus externally owned writes must not be mixed. Proposed safe external ownership is not yet a validated deployed topology. |
| SK-006 | Medium / clarification | spec scope/Q-004; clarifications | Plan-derived defaults selected; evaluator taxonomy/language criteria still unknown. No false claim of individual user answers. |
| SK-007 | Medium / workload ambiguity | spec Q-006; scale design | Billion URLs/large reads lack agreed window/skew/freshness/retention. Variable model and explicitly hypothetical arithmetic, not capacity claim. |
| SK-008 | Resolved / semantics | data model; D-032 | Month is source/reporting context and differs from observed time; no historical-content promise. |
| SK-009 | Medium / standards | feature checklists | Requirements quality and implementation evidence are separate. No authoritative Python/Argo/Iceberg kit coverage is invented; reviewer boxes untouched. |
| SK-010 | Resolved with condition / assignment coverage | release/estimate docs | Part 3 conditional effort estimates retained; actual deadline and authorization wait are not invented. |
| SK-011 | Medium / quality | evaluation/labels | Six AI-authored synthetic cases are not a human held-out relevance study; topic weaknesses disclosed. |
| SK-012 | Medium / observability | NFR-006; T15 | Basic queue/readiness metrics implemented, broader timing/tracing/cost/alert/fault evidence remains remote hardening. |
| SK-013 | Medium / source integrity | T06; ingestion | Local file and query-contract tests do not prove actual MySQL snapshot/index/UTC/GCS behavior. Real source tests remain gated. |
| SK-014 | Medium / data lifecycle | FR-014; runbook | No destructive retention/deletion job enabled. Owner must define lawful cross-object/snapshot/backup policy before production. |
| SK-015 | Medium / reproducibility | NFR-008; deploy profiles | Version lock exists but no artifact hashes/remote image build/digests or installed cluster-schema validation; placeholders deliberately remain blocked. |
| SK-016 | Resolved / model drift | data-model.md; plan sections 3/5/6 | Flat modules, actual field names, epoch-to-UTC mapping, attempt-count-only POC, canceled nonpublication, day partitioning and bounded-shard limits reconciled with implementation. |

No current missing core artifact, conflicting mandatory technology/service rule,
or zero-task baseline requirement was found. There are **no current critical
artifact contradictions** in this pass; high findings remain visible and block
the affected final gates. This is not a waiver or a zero-defect certification.
No material duplicate requirements were identified; overlapping safety/recovery
requirements describe separate observable boundaries.

## Requirement-to-task inventory

These are **planned task links**, not completion/adoption percentages.

| Requirement | Tasks |
|---|---|
| FR-001 | T02,T05 |
| FR-002 | T03 |
| FR-003 | T03,T12,T15 |
| FR-004 | T03,T05 |
| FR-005 | T02,T04 |
| FR-006 | T02,T04 |
| FR-007 | T02,T04 |
| FR-008 | T02,T03,T04 |
| FR-009 | T05,T09,T15 |
| FR-010 | T05,T06 |
| FR-011 | T06 |
| FR-012 | T02,T07,T10 |
| FR-013 | T05 |
| FR-014 | T05,T07,T09 |
| FR-015 | T08,T10,T11 |
| FR-016 | T10,T11 |
| FR-017 | T08,T12 |
| FR-018 | T13,T14 |
| FR-019 | T07,T11,T12,T14,T15 |
| FR-020 | T18 |
| FR-021 | T16 |
| FR-022 | T16,T19 |
| FR-023 | T15,T19 |
| FR-024 | T19 |
| FR-025 | T01,T09,T19 |
| FR-026 | T17,T19 |
| FR-027 | T03,T04,T20 |
| FR-028 | T21 |
| NFR-001 | T06,T07,T16 |
| NFR-002 | T05,T16 |
| NFR-003 | T15,T19 |
| NFR-004 | T03,T09,T15 |
| NFR-005 | T05,T07,T11,T15 |
| NFR-006 | T15 |
| NFR-007 | T08,T13,T16,T19 |
| NFR-008 | T01,T09,T17,T20 |

Current inventory: 28 FRs, 8 NFRs, 11 acceptance scenarios, 55 decisions,
9 question IDs, 21 tasks and 26 research IDs. All 36 formal
functional/nonfunctional requirements have at least one planned task link;
none of the 21 tasks is unmapped. The task
prerequisite graph is acyclic. Acceptance scenarios trace to local tests or
explicitly blocked remote/public/quality gates; they are not all passed.

## Failure-fix consistency follow-up

D-037 through D-040 / R-019 refine T03/T04/T05/T07 under existing FR-003 through
FR-005, FR-008 and FR-012: independent bounded wire/decoded budgets, correct
document title, preserved status/stage context and status-first error handling.
Settings, environment examples, plan, runbook, data mapping and evaluation were
reconciled. Failure context uses the existing metadata map/JSON representation,
not an untested schema migration. No requirement IDs or task dependencies changed.

Actual evidence is 66 passing tests / one gated cloud skip plus a fresh real TCP
API/worker/local Iceberg run: CNN success, Amazon 503 and REI robots 403.
All-terminal jobs do not mean all successful extractions. Broader topic quality,
full attempt history and remote/public gates remain open. This is a manual delta
consistency review, not a new automatic Spec Kit command execution.

## Next actions and checklist boundary

Readiness correction D-041 through D-043 / R-020 refines T04/T16 under
FR-005/FR-006/FR-007/FR-021: live-fetch success is separate from useful,
complete content and relevant topics. Generic structured-content, product and
boilerplate fixes carry v2 provenance in the existing schema. At that snapshot,
evidence was 70 passing tests / one cloud skip, 8/11 selected live fetches, eight paired
same-HTML checks and a remeasured 131/s synthetic extraction stage. These are
not independent relevance scores, random web-success rates or production SLOs.
The conservative robots policy is explicitly stricter than RFC's optional 4xx
permission; an unrequested article has no observed denial. No requirement IDs,
task dependencies or reviewer assertions were changed.

Local implementation can be reviewed using real tests/measurements. Complete the
owner's resource decisions, interoperability spike, real remote/fault evidence,
independent quality review, immutable image/security/license checks and public
HTTPS smoke test before final release. Re-run the pinned semantic procedure after
changing taxonomy, provider/catalog ownership, source semantics or schema.

## Architecture-delta consistency analysis

Manual delta review of the user's architecture request reconciles D-044 through
D-050 / R-021 through R-024 with existing FR-002 through FR-008, FR-012/FR-014,
FR-023/FR-027 and T03/T04/T05/T07/T09/T15/T16/T18. The reusable pipeline and
opt-in JS-shell profile explicitly supersede the earlier no-rendering default
boundary without turning error pages into successful content. No raw browser
egress, remote crawling/NLP service, automatic query-identity rewrite or
unrequested model download was added.

The API remains asynchronous/durable rather than introducing a competing sync
endpoint; library equivalents are documented. New operational fields and
weighted topic scores are explicitly preserved in existing analytical metadata,
not silently discarded from the fixed physical topic struct. Logical schema 1
and immutable old generations remain compatible; source versions change to v3.
Confidence is evidence-based text, not an invented calibrated probability.

Verified evidence: 89 tests pass/one cloud skip with real browser tests enabled;
all project checks pass. Six live inputs yield three content results and three
explicit failures, all six local Iceberg rows verified. Offline same-HTML topic
cleanup preserves bodies/types. Browser image authoring is not build, Linux
sandbox validation or deployment. V3 throughput, independent topic quality,
remote/catalog/engine/public gates remain open. No new requirement/task IDs,
dependencies or reviewer checkbox assertions were introduced. This is a manual
pinned-procedure consistency analysis, not a fabricated slash-command run.

The actual pinned `check-prerequisites.ps1 -Json -RequireSpec -RequireTasks
-IncludeTasks` invocation also passed against the explicit feature directory;
its output is retained in `evidence\architecture-spec-prerequisites.json`.
This verifies artifact presence/resolution, not semantic quality or a completed
modern CLI lifecycle.

`evidence\architecture-documentation-validation.json` verifies the reconciled
ID inventories, preservation of all three original inputs, environment defaults,
optional dependency disclosure and all 20 retained passing-code/manifest hashes.
Documentation-only reconciliation did not change that tested implementation.

## Optional UI delta analysis

Manual follow-up for D-053/R-025/FR-028/AC-011 adds T21 depending on T05.
The original backend-only boundary is explicitly superseded by the user's
later UI authorization and confirmed design context. The same-origin static
workspace reuses existing job and auth contracts; exact-job body retrieval
avoids mixing generations from the mutable latest-document projection.
No data-model migration or external frontend/runtime/service is introduced.
New asset package-data and real-browser tests cover the added surface.

The prior architecture sections describe their dated snapshots, not the
later D-051 robots policy or D-052 native browser behavior. D-052 has weaker
network/resource isolation than D-046 and can use a headed window; UI success
does not validate native redirects/subresources, Linux cloud compatibility,
arbitrary-site access, or deployment readiness. See `poc-guide.md` for the
current distinction. Remote/public/quality/security/human release gates remain
open. UI verification commands/results are retained in
`evidence\ui-validation.json`; reviewer boxes remain untouched. This is a
manual delta consistency check, not a new automatic Spec Kit command run.

The subsequent D-054/R-026 delta extends existing FR-028/AC-011/T21 with both
single and multiple URL modes. Existing API cardinality, payload/auth/rate limits,
job identity and whole-batch validation stay unchanged. Normalized duplicates
share a row; mixed outcomes and exact-job bodies remain separate. Sequential
bounded polling avoids a per-job request burst against the existing quota.
Documentation distinguishes current snapshot export from terminal success and
selected-job cancellation from batch-wide cancellation. No new formal requirement,
task dependency, storage schema or remote gate is introduced. Actual follow-up
evidence is in `evidence\ui-batch-validation.json`.

D-055 relocates the API/UI Dockerfile to the repository root under existing
T09/FR-025. Its instructions, root build context and port are unchanged; the
browser-worker Dockerfile remains under `deploy`. Deployment instructions now
name the root path. This layout change does not diagnose the failed cloud build
or supply a container-build/deployment result; cloud logs remain unavailable.

Human checklists are unchanged. This report does not assign SDD maturity or
normalized coverage scores. Full modern CLI integration can be installed
project-locally when the tooling/network issue is resolved; do not silently
upgrade the user's global tools or mislabel the existing manual work.
