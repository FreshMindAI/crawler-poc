# Assignment coverage and submission boundaries

| Obligation | Concrete artifact / status |
|---|---|
| Part 1 generic crawler, metadata/body, page type/topics | `src\crawler_poc`, API/worker CLI and tests; implemented locally |
| Optional neutral POC UI | Bundled `ui` assets, exact-job body API, browser workflows; local verification in `docs\evidence\ui-validation.json`, not a public deployment |
| User architecture refinements | `pipeline.py`, optional `rendering.py`, richer v3 output, six-input manifest and `docs\architecture-alignment.md`; real browser fixture and six-row local publication evidence |
| Part 1 public cloud demo | **Incomplete** pending authorized Azure/GCP deployment and external evidence |
| Part 2 monthly file/MySQL ingestion and unified persistence | Streaming adapters, lineage/control schema and Iceberg writer; real MySQL/PostgreSQL/GCS validation still gated |
| Part 2 billion-URL/large-read architecture, cost/reliability/performance/SLO | `docs\scale-design.md`, `runbook.md`, raw local benchmark evidence |
| Required Iceberg | Real local v2/Parquet commits, observed-day partition and post-commit replay test |
| Required Trino | Real HTTPS query adapter/SQL/profile implemented; **remote execution incomplete** |
| Required Argo | Bounded source-ref/four-worker/publish/reconcile/report DAG/RBAC implemented; **remote execution incomplete** |
| Required BigQuery | Real SDK/parameterized/billed-bytes-capped query and opt-in test implemented; **GCP execution incomplete** |
| Part 3 POC, blockers, quality, schedule/effort and release | Evaluation, remote gates, release plan, conditional estimate and unchecked review checklists |
| AI/library/service rules | `docs\ai-usage.md`, dependency metadata, no equivalent turnkey crawler/NLP services |
| Spec Kit decisions/research/architecture/open questions | `.specify` and `specs\001-crawler-poc`; transparent manual analysis/fallback record |

Include source, tests/fixtures, examples, base/optional-browser locks, specifications, deploy/SQL
templates, notices and documentation/evidence. Exclude `.venv`, `.git` internals,
secrets/`.env`, caches, all `var` data/databases/raw pages, private cloud configs,
build artifacts and local credential files. Git publication and cloud deployment
are separate actions; this manifest does not prove that the current checkout has
been pushed or deployed. No assignment submission archive is produced by this change.

The reviewer-owned checklists remain unchecked. Missing access does not waive
public demo, genuine mandatory-stack execution, human review or release gates.
