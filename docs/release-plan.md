# POC-to-release plan and blockers

## Current gates

| Gate | State and evidence |
|---|---|
| G0 specification baseline | Pinned source templates, reviewed requirements/decisions and manual semantic analysis; full modern CLI lifecycle did not execute |
| G1 local core | Implemented and tested; synthetic quality limitations and original URL failures are disclosed |
| G2 remote data stack | **Blocked**: no authorized cluster/catalog/Trino/Argo execution or image build |
| G3 BigQuery | **Blocked**: no approved GCP project/IAM/billing/table topology or real query |
| G4 local evaluation | Baseline 10k/100k stage measurements retained; human quality, sustained API and remote load tests remain |
| G5 public demo | **Blocked**: no hosting/TLS/ingress/budget authorization or external HTTPS evidence |
| G6 submission release | **Not passed**: depends on G2/G3/G5, remote hardening and human release assertions |

## Remaining sequence

Authorize non-secret environment inventory and spending boundaries first. Build
an immutable image with an approved remote builder, validate namespace manifests
against installed versions, and complete the catalog/version/authentication
spike. Stop if externally owned Iceberg cannot be safely read by both engines;
record an approved alternative rather than mixing BigQuery-managed writers.

Run a tiny fixture publication and compare schema/nulls/Unicode/timestamps/topics,
counts and normalized values through both engines. Exercise a second publication,
commit-before-ack, expired tokens and worker/workflow termination. Then run the
bounded Argo shard DAG with source accounting and retained query/job evidence.

Human-review a diverse held-out relevance set, repeat stage measurements and add
end-to-end controlled-network/storage/API workloads on the declared deployment
profile. Define budgets, data retention and proposed SLO measurement windows.
Validate realistic payload/host skew; do not load-test public target sites.

Deploy an authenticated HTTPS canary only after ingress/egress/IAM/secret/backup
controls and cost limits are approved. Run genuine external submit/poll/latest/
body/cancel/auth/limit checks. Record image/config/table identity and rollback
reference. No schema migration system exists yet; plan forward/backward schema
compatibility before altering a retained database.

## Release controls

- Run pytest, Ruff check/format, mypy and Spec Kit consistency/artifact checks;
  validate SQL, Kubernetes and Argo against actual pinned remote versions.
- Scan dependencies/image and source for vulnerabilities/secrets using the
  approved environment tools; review the generated license inventory. These
  cloud/image/security scans have **not** run locally.
- Preserve source/input/publication lineage, retained measurement outputs and
  honest limitations. Never tick human-owned checklist boxes automatically.
- Roll back app/image/config compatibly; preserve SQL state, objects and
  committed Iceberg snapshots. Replay ambiguous batches only through the ledger.
- Teardown only named authorized POC resources, remove public ingress/keys and
  apply the agreed lawful retention policy; do not delete shared resources.

The assignment's actual deadline/receipt acknowledgment/submission destination
remain owner/evaluator inputs. No email, repository push, upload, spend or public
deployment has been performed.

## BrightEdge Weekly Release Train Integration

Every change is structured to ship safely inside a **weekly release train**:
1. **Immutable Versioned Provenance:** Every crawled record stamps `normalization_version`, `fetcher_version`, `extractor_version` (`html-trafilatura-v3`), and `classifier_version` (`schema-rules-yake-weighted-v3`). Weekly improvements to extraction or topic weighting ship under a new version string and `generation` without schema migrations or rewriting prior weeks' Iceberg snapshots.
2. **Runtime Feature Flags:** Expensive or environment-sensitive capabilities (`CRAWLER_BROWSER_FALLBACK`, `CRAWLER_BROWSER_MAX_REQUESTS`, `CRAWLER_MAX_BYTES`, `CRAWLER_ORIGIN_DELAY`) are controlled via environment configuration so an operator can degrade gracefully to static HTTP in seconds during a weekly rollout.
3. **Canary & Automated Gate per Week:** CI runs `pytest` (91 tests), `ruff`, `mypy`, `pip check`, and synthetic quality evaluation (`crawler evaluate`) before image promotion, followed by the 4-week rollout schedule in `docs\implementation-estimate.md`.
