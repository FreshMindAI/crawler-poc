# Crawler POC constitution

Version: 0.2.0  
Last amended: 2026-11-14  
Status: implementation baseline applied under the approved plan and build request.
Independent human review/release assertions remain outstanding.

## I. Assignment fidelity

Deliver a functioning generic URL crawler/classifier and public demo, plus the billion-URL operations design and POC/release documentation. Trace requirements to the three-page assignment. Do not present an architectural proposal, a mock, or a small benchmark as production proof.

External HTTP/HTML/NLP/data libraries are allowed. Managed crawling/scraping, page-extraction APIs, outsourced topic-classification APIs, protection-bypass services, and equivalent turnkey services are prohibited. No runtime external LLM dependency is permitted in the proposed baseline.

## II. Python-first, evidence-led performance

Target Python 3.12 initially. Use bounded asynchronous I/O, native parsing/columnar libraries, streamed input and batched output before considering a language rewrite. Rust requires a profile demonstrating a bottleneck, a measured comparison, packaging/maintenance justification and explicit approval.

Pin dependencies and engine/container versions during bootstrap. The proposed Iceberg format is v2/Parquet; package versions and catalog compatibility remain unverified until the integration spike.

## III. Safe and polite crawling

Only fetch public HTTP(S) destinations through a guarded network path. Validate DNS answers and actual connection destinations, including redirects and robots requests. Deny private/special-use/cloud-metadata destinations and embedded credentials. Respect robots policy, target-site terms, finite time/size/retry budgets, per-origin limits and cancellation.

Never bypass CAPTCHA, paywalls, login, robots rules or access controls. Return explicit blocked/unsupported/error outcomes instead of inventing content.

## IV. Architecture and ownership

Use a modular service with separate transport, admission/scheduling, extraction, classification, persistence, publication and API boundaries.

Separate the operational serving/control store from the Iceberg analytical history. Trino and BigQuery query analytics; Argo orchestrates bounded batch/shard execution, not one task per URL. A table has one declared publication/maintenance ownership domain; do not mutate BigQuery-managed files externally.

## V. Durability without exaggerated guarantees

Assume at-least-once delivery. Use idempotency keys, stable identities, leases with fencing, bounded retries, an outbox/publication ledger and reconciliation. Make duplicate-free effective results testable. Do not claim distributed exactly-once processing merely because an Iceberg snapshot is atomic.

## VI. Tests and evidence

Use pytest and focused asynchronous tests for introduced behavior. Add regression cases for safety, concurrency, malformed input, partial failures, replay and schema changes. Use hand-authored or appropriately licensed fixtures with provenance.

Record benchmark environment, input distribution, versions and raw outputs. Keep manual quality labels separate from implementation rules. Use the same evaluation corpus for baseline and optional local pretrained NLP comparisons.

## VII. Security and data handling

No secrets in source, specs, notebooks, manifests, logs or submissions. Use least-privilege workload identities or approved secret storage. Authenticate and rate-limit public write endpoints. Redact sensitive URL query values and never log full HTML/body content by default.

Keep raw objects private; serve bounded text/metadata, never executable retrieved HTML. Track retention, deletion and access requirements for crawled content.

## VIII. Deployment boundaries

Azure/GCP hosting is undecided. BigQuery requires authorized GCP resources. All Kubernetes/Trino/Argo integration runs target an explicitly approved remote environment. Do not install local container/Kubernetes infrastructure, change shared cluster-wide resources, or spend without separate approval.

Pure Python tests may use local files/SQLite and controlled test servers; they are not substitutes for remote integration evidence.

## IX. Spec-driven change control

The specification owns requirement IDs and the decision register. Every material change records status, alternatives, rationale, evidence and consequences. Proposed choices are not human approvals.

Execute the selected pinned Spec Kit clarify/checklist/analyze procedures and
retain their evidence before implementing a slice. If the CLI/integration cannot
run, record the failure and the explicit manual agent procedure used; never label
that as an executed slash command. Record ordering deviations as findings rather
than rewriting history. Requirements-quality and implementation-verification are
different gates. Reviewers own checklist assertions; automated checks are not
quality certification.

## X. Honest release and AI disclosure

Document all AI tools actually used and how they assisted. Record dependency/model licenses, service inventory, known limitations, public demo evidence, rollback/teardown procedures and unresolved risks.

The final assignment must address scheduling/estimation with stated assumptions after validation. Do not fabricate delivery promises or report deferred BigQuery/public-hosting work as complete.

## Amendment record

0.2.0 records implementation adoption and a transparent pinned-procedure fallback
for the failed modern CLI bootstrap (D-027). Safety, no-service-substitution,
resource authorization, reviewer ownership and real remote-evidence gates are
unchanged. Initial code preceded retained post-bootstrap semantic analysis; that
process deviation remains visible in `docs\speckit-analysis.md`.
