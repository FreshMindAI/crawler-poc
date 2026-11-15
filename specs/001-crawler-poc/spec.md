# Feature specification: safe crawler and scale POC

Status: implementation baseline under the approved plan and "build it" request.
Local code/tests/evidence exist. Public deployment and real remote-stack
verification remain blocked on separate resource authorization.

## 1. Problem and users

Given a URL, obtain HTML metadata and readable content, classify the page, and return relevant topics. Demonstrate the service publicly, then explain and validate a path to processing billions of supplied URLs while supporting large read workloads economically and reliably.

Primary users: an API consumer requesting a crawl/result; an operator submitting a monthly URL collection; an evaluator reviewing correctness, scale design and release evidence.

## 2. Sources and binding constraints

| Source | Constraint or obligation |
|---|---|
| Assignment p.1 | Generic core crawler; page classification and relevant topics; consider the supplied examples |
| Assignment p.2, Part 1 | HTML metadata including title, description and body; runnable public-cloud demo |
| Assignment p.2, Part 2 | Billions of URLs supplied by text file and/or MySQL with year-month context; unified metadata/content storage; cost, reliability, performance and scale; SLO/SLA and monitoring |
| Assignment p.2, Part 3 | POC engineering breakdown, blockers, evaluation, implementation scheduling/estimation and quality-release documentation |
| Assignment p.3 | Libraries and cloud infrastructure allowed; equivalent third-party functionality services prohibited; AI assistance must be disclosed |
| User clarification | Mostly Python; profile before Rust; use BigQuery, Trino, Argo Workflows and Iceberg |
| User clarification | Backend scope; 10k-100k controlled records; local pretrained NLP backup/benchmark documented |
| User clarification | Azure/GCP hosting discussion later; authorized remote Kubernetes rather than local infrastructure |

Sample pages are an Amazon product, an REI outdoors article and a CNN technology article. Preserve their exact source links from the PDF when assembling the live-test manifest; do not repair or replace dead links silently. Amazon/Walmart/Best Buy are examples of input domains, not permission to exhaustively crawl them.

## 3. Scope

### In scope

- Single supplied URL and bounded multi-URL API admission; streamed text-file input and a read-only MySQL ingestion adapter.
- Safe fetching, HTML metadata/body extraction, generic page-type classification and ranked local topic/keyphrase extraction.
- Durable job lifecycle, per-origin scheduling, retries, deduplication, result storage and API lookup.
- Remote-executable Iceberg/Trino/Argo integration and real BigQuery adapter/query evidence once access is approved.
- Tests, controlled benchmarks, capacity/cost/operations design, POC evaluation, release plan and AI disclosure.

### Selected POC defaults under plan approval

- Fetch supplied URLs rather than recursively discover the web.
- Static HTTP baseline plus optional bounded Playwright rendering of successfully
  fetched JavaScript shells under the user's later architecture request (D-044
  through D-046); no protection bypass.
- English-first quality evaluation; preserve Unicode metadata and report unsupported topic-language cases.
- Return asynchronous job IDs and poll/read results; do not hold API requests open for a complete crawl.
- Public endpoints require authentication, admission limits and abuse protection; a custom UI is excluded.

### Out of scope

- Actually crawling billions of pages or demonstrating millions of live requests during the assignment.
- Turnkey crawling/extraction/classification services, external LLM inference and CAPTCHA/proxy-evasion services.
- Local Kubernetes/Docker installation, unauthorized remote access, unapproved spend or automatic use of existing organizational subscriptions.
- Historical web reconstruction from current URLs, unless the evaluator supplies historical content.

## 4. Functional requirements

| ID | Observable requirement |
|---|---|
| FR-001 | A caller can submit a public HTTP(S) URL and obtain a stable job ID, then retrieve status and a structured terminal result. |
| FR-002 | Invalid schemes, credentials-in-URL, disallowed ports and private/special-use destinations are rejected before content is fetched; DNS and redirect changes cannot evade this rule. |
| FR-003 | The crawler evaluates robots policy for the correct origin/user agent and records the decision; disallowed content is not fetched. Robots redirects and errors follow a documented bounded policy. |
| FR-004 | HTTP operations have finite concurrency, redirect, retry, timeout and compressed/decoded-size budgets. A limit breach produces an explicit outcome rather than unbounded work. |
| FR-005 | Successful HTML results contain title, description, readable body, headings, language evidence, canonical-link candidate, selected social/structured metadata and provenance; missing values are explicit. |
| FR-006 | Page type is inferred generically from content/structured evidence, returning a documented type such as product/article/category/home/other/unknown and the rule/version/evidence used. |
| FR-007 | Results include bounded ranked topics/keyphrases, extraction method/version and supporting evidence; keyword scores are not misrepresented as calibrated probabilities. |
| FR-008 | Removed, blocked, non-HTML, insufficient-content and unsupported pages have distinguishable outcomes and are not classified as successfully extracted pages. |
| FR-009 | Jobs survive worker restarts and support bounded retries, cancellation and expired-lease recovery without stale workers overwriting newer results. |
| FR-010 | Duplicate submissions and repeated processing of the same logical work have specified idempotency semantics; source aliases are retained without duplicate effective results. |
| FR-011 | Text/MySQL input is streamed by bounded batches with year-month/source identity, checkpointing and invalid-record accounting, without loading the complete collection in memory. |
| FR-012 | API JSON, operational records and analytical records map to one versioned logical schema with stable IDs, UTC timestamps, nullability and explicit outcome fields. |
| FR-013 | Consumers can read latest metadata/topics and bounded body text without requiring a fresh crawl or per-request Trino/BigQuery scan. |
| FR-014 | Content is retained as private objects with content hashes, references, retention/deletion policy and provenance; logs do not contain raw content or sensitive URL values. |
| FR-015 | A real Iceberg table receives bounded published batches through a declared catalog/commit owner, preserving schema/version identity and a replay-verifiable publication ID. |
| FR-016 | Real Trino queries over that table demonstrate result access, reconciliation and partition-aware queries, not just connection configuration. |
| FR-017 | A real Argo workflow drives bounded ingest/shard processing/publication/reconciliation with retries, cancellation and artifact references; individual URLs are not workflow nodes. |
| FR-018 | A real BigQuery query validates the intended Iceberg publication or an explicitly documented materialized projection; a local emulator/mock cannot satisfy this requirement. |
| FR-019 | Publication replay and partial failures reconcile source counts, job outcomes, content references and analytical results; crash-after-commit recovery does not append duplicates. |
| FR-020 | The core service is reachable on an approved public Azure/GCP endpoint with authenticated examples and genuine live smoke-test evidence. |
| FR-021 | Reproducible correctness/quality tests and controlled 10k-100k-record performance tests report actual measured results and failure/resource breakdowns. |
| FR-022 | The production design models billion-URL ingestion, large read demand, host skew, storage/network/query costs, backpressure, retention and failure domains with explicit assumptions. |
| FR-023 | Documentation defines proposed SLOs, SLIs, exclusions, monitoring/alerts, error-budget handling and SLA limitations rather than claiming contractual guarantees from a short demo. |
| FR-024 | POC/release documentation covers engineering sequence, known versus uncertain work, blockers, experiments, acceptance criteria, rollback, rollout and final scheduling/estimation assumptions. |
| FR-025 | Submission includes runnable instructions, configuration examples, source/dependency/model/service inventory, licenses, limitations and a truthful AI-assistance disclosure. |
| FR-026 | A local pretrained NLP alternative is documented as a backup, with an opt-in comparison plan using the same quality corpus and resource measurements. |
| FR-027 | Runtime crawling, extraction and classification remain in the submitted implementation and its libraries, not outsourced to an equivalent third-party service. |

## 5. Non-functional requirements

| ID | Requirement and proposed verification |
|---|---|
| NFR-001 | Bounded memory: fixed-size queues and batches; the controlled 100k input does not require proportional in-memory materialization. Record steady-state RSS at fixed concurrency and explain growth. |
| NFR-002 | Performance evidence separates fetch, parse/classification, persistence/publication and API lookup. A provisional warm lookup p95 target is 250 ms on a declared controlled environment; it is not a measured result or external SLA. |
| NFR-003 | Availability target for design: 99.9% successful eligible API requests over an explicitly chosen reporting window. External-site denial/absence is a crawl outcome, not automatically an API availability failure. Final windows/exclusions need owner agreement. |
| NFR-004 | Safety: disallowed network fixtures produce zero forbidden outbound requests. The production network additionally enforces egress restrictions; application checks alone are not the only control. |
| NFR-005 | Data integrity: replay/concurrent-worker/failure tests preserve unique effective event identity, complete source accounting and valid content references. |
| NFR-006 | Observability: every logical job has a correlation ID; low-cardinality metrics expose queue age, throughput, retries, outcomes, host throttling, resources, publication lag, query scans and costs. |
| NFR-007 | Cost: no unapproved spend; benchmarks and design report cost drivers per processed URL and per analytical/serving workload. Pricing estimates must identify region, assumptions and source. |
| NFR-008 | Reproducibility: dependency locks, immutable image references, schema versions, fixture provenance, model revisions and benchmark parameters accompany evidence. |

Concrete client limits belong to the approved API/configuration contract. Suggested starting bounds are documented in the technical plan and remain proposals.

## 6. Acceptance scenarios

| ID | Given / When / Then |
|---|---|
| AC-001 | Given a permitted hand-authored product/article fixture, when it is crawled, then title/body/page type/topics and provenance meet its expected labels. |
| AC-002 | Given a URL resolving or redirecting to a private/special-use destination, when submitted, then fetching is blocked and the forbidden test server observes no request. |
| AC-003 | Given robots disallow, robots unavailability, 429, 404, non-HTML, malformed HTML, oversized content or a JavaScript shell, when processed, then the documented bounded outcome is returned without invented metadata/topics. With rendering explicitly enabled, a permitted 200 JS fixture can produce extracted content; policy/error/challenge responses never escalate. |
| AC-004 | Given duplicate input and a worker crash/restart, when the same generation is replayed, then aliases remain traceable and effective successful results are not duplicated. |
| AC-005 | Given text/MySQL input with invalid/duplicate records and a selected source month, when processed, then checkpoints resume and input/job/publication counts reconcile. |
| AC-006 | Given the authorized remote integration environment, when a controlled run completes, then real Argo execution and Trino queries over Python-published Iceberg data have retained evidence. |
| AC-007 | Given later approved GCP access, when BigQuery validates a publication, then its normalized row counts/sample aggregates match Trino for the same publication/snapshot definition. |
| AC-008 | Given the controlled benchmark corpus, when baseline and optional pretrained methods are evaluated, then quality and resource costs are reported with versions and no unmeasured speed claims. |
| AC-009 | Given approved public hosting, when an authorized external client follows the quickstart, then submit/poll/result works and abusive/unauthorized input is rejected. |
| AC-010 | Given the submission bundle, when evaluated against Parts 1/2/3, then every requested deliverable has a concrete artifact and remaining limitations are disclosed. |

## 7. Entities and physical mapping

| Logical entity | Proposed physical location | Requirements |
|---|---|---|
| Source manifest/input record | `crawl_runs`, `input_records`; immutable manifest objects | FR-010, FR-011, FR-019 |
| Job/attempt/origin state | `crawl_jobs`, `crawl_attempts`, `origin_state` | FR-003, FR-004, FR-009 |
| Latest document/result | `documents_latest` and bounded content endpoint | FR-005 through FR-008, FR-013 |
| Raw/clean content | Private content-addressed objects | FR-014 |
| Publication/outbox | `result_outbox`, `publish_batches` | FR-015, FR-019 |
| Analytical crawl event | Iceberg `crawler.crawl_events` | FR-012, FR-015, FR-016, FR-018 |
| Model/evaluation record | Versioned evaluation artifacts | FR-021, FR-026 |

Column-level mappings and invariants: `data-model.md`.

## 8. Decision register

All material implementation decisions must be added here or amend the existing row. Status does not imply user approval. Research IDs resolve in `research.md`.

The original D-010 through D-025 proposals below preserve planning history.
Their implementation selections are reconciled by D-027 through D-050; they were
selected under plan/build authorization, **not separately answered user questions**.
Cloud account/catalog/hosting choices remain deferred.

| ID | Status / authority | Decision, alternatives and rationale | Consequence / evidence |
|---|---|---|---|
| D-001 | Confirmed / user | Use `<repo-root>`, not an existing repository. | Greenfield; create only after approval. |
| D-002 | Confirmed / user | Python-first; Rust only after a measured bottleneck, rather than a speculative rewrite. | Profile native-library/async pipeline first. |
| D-003 | Confirmed / user | Backend/API and engineering evidence; no custom UI. | API documentation/examples are the demo interface. |
| D-004 | Constraint / assignment and user | Libraries allowed; equivalent managed crawling/extraction/classification services prohibited. | Audit dependency and outbound-service inventory; FR-027. |
| D-005 | Confirmed / user | Iceberg, Trino, Argo and BigQuery are implementation deliverables. | Real integration evidence is required; not diagram-only. |
| D-006 | Deferred / user | Hosting is Azure or GCP; provider/account/region/budget undecided. | No deployment/spend; BigQuery still requires GCP. |
| D-007 | Confirmed / latest user clarification | Use authorized remote Kubernetes, not local infrastructure. | Remote profiles replace the earlier local-profile suggestion. |
| D-008 | Confirmed / user | Use local explainable NLP baseline and record pretrained backup/benchmark. | No hosted NLP API; R-005/R-006. |
| D-009 | Confirmed / user | Benchmark controlled 10k-100k records; design, not execute, billion-URL scale. | Keep measured and modeled figures separate. |
| D-010 | Proposed | Supplied URLs, static HTML, English-first evaluation; alternative is recursive/rendered/multilingual crawling. | Keeps POC bounded; Q-004 requires confirmation. |
| D-011 | Proposed | Async submit/poll/read with authenticated/rate-limited public admission instead of blocking crawl requests. | Proposed API contracts in technical plan. |
| D-012 | Proposed | aiohttp plus native HTML parsing, Trafilatura and YAKE; Scrapy remains an alternative. | Smaller targeted-URL pipeline; validate safety/quality/performance; R-002 through R-005. |
| D-013 | Proposed | Local SQLite/files adapter for pure core development; remote PostgreSQL/private objects for integrated POC. | No local infrastructure installation; neither is a claim of production-billion-scale serving. |
| D-014 | Proposed | Iceberg v2/Parquet, bounded columnar batches and a shared REST catalog rather than raw Parquet mislabeled as Iceberg. | Cross-engine compatibility spike; R-007/R-008. |
| D-015 | Proposed, catalog choice deferred | Prefer externally owned Iceberg with read-only BigQuery access; avoid unsupported mixed writers. | BigQuery-managed tables require BigQuery-owned writes; R-009/R-010. |
| D-016 | Proposed | Single publication/maintenance owner per table in POC, replay ledger and snapshot-aware acknowledgment. | Prevent duplicate append on ambiguous commit; FR-019. |
| D-017 | Proposed | Argo schedules bounded shards, never one pod/node per URL. | Scheduler fairness is inside workers/control plane; R-011. |
| D-018 | Proposed | Online read projection/cache separate from analytical Iceberg scans. | BigQuery/Trino are not API lookup databases. |
| D-019 | Proposed | Bounded retries, conservative origin pacing, robots compliance and no bypass. | Sample sites can legitimately fail; R-012/R-013. |
| D-020 | Proposed | Conservative URL normalization preserves query semantics; discovered canonical URLs are evidence, not automatic identity rewrites. | Avoid merging distinct pages or breaking signed/query-sensitive URLs. |
| D-021 | Proposed | Distinct reporting month, observed timestamp, logical generation and publication identity. | A month-filtered source does not imply historic page retrieval; Q-005. |
| D-022 | Proposed | Pin compatible Spec Kit tooling project-locally after approval, not a silent global upgrade. | Installed 0.0.22 differs from current upstream interface; R-001. |
| D-023 | Constraint / planning mode | Keep all current documents in the session workspace. | No initialized project or genuine Spec Kit command execution is claimed. |
| D-024 | Proposed | Optional local KeyBERT-style comparison; no model downloads in planning. | License, artifact revision and CPU/RSS/quality must be checked; R-006. |
| D-025 | Proposed | Public content remains private at rest; return text safely and redact logs. | No public raw-content bucket or live HTML rendering; FR-014. |
| D-026 | Deferred / assignment follow-up | Produce final schedule/estimation documentation after environment/scope validation. | No invented time/date estimates in this plan; FR-024. |
| D-027 | Implementer / approved build | Apply the pinned Spec Kit source procedures with retained manual semantic analysis when modern CLI bootstrap cannot run. Keep source provenance, global CLI unchanged and ordering deviations visible. | `.specify\bootstrap.json`, `docs\speckit-analysis.md`; not a fabricated slash-command lifecycle. D-022/D-023 superseded for implementation location/process. |
| D-028 | Selected POC defaults / approved plan | Supplied static URLs, English-first free keyphrases, async API with a single operator API key, four workers by default; lxml/Trafilatura/YAKE and SQLite/files locally. | Implements D-010/D-011/D-012/D-013; no rendering, taxonomy training or multi-tenant identity. Unknown language assumes English. |
| D-029 | Implementer / safety and scale | Bound bodies/requests/time/redirects/attempts, guard connector DNS and every redirect, use configured robots product token and shared DB origin leases. Admission counts nonterminal jobs plus unpublished events. | D-019/D-020 selected; defaults/config/policy in `docs\runbook.md`; network egress still a deployment gate. |
| D-030 | Implementer / reliability | Preserve URL/generation/top-k/principal job identity, token-fenced leases, latest successful generation and transactional outbox. Canceled jobs are terminal but not analytically published. | D-018 selected; attempts counted, not a full historical attempt table; explicit recrawl generation required. |
| D-031 | Implementer / interoperability | Real Iceberg v2/Parquet, observed-day partition, bounded deterministic batches, batch-ID predicate overwrite/replay check, one publisher/maintenance ownership domain. | D-014/D-016 selected; local commit/replay verified. REST catalog choice, Trino/BigQuery visibility/auth remain blocked, not replaced by local SQL. |
| D-032 | Implementer / input contract | Source month is UTC input/reporting context, not past HTML. Local file fingerprint and GCS generation pin input identity; MySQL requires immutable rows, positive monotonic integer ID, fixed selected columns and high watermark. | D-021 selected; line/row aliases, invalids and checkpoints persist. Real MySQL/GCS source behavior still needs remote validation. |
| D-033 | Implementer / bounded orchestration | One bounded source-object shard, four fixed worker pods, isolated batch control DB, publish/reconcile/real report stages; production external manifest scheduler is design work. | D-017 selected; no URL-sized Workflow arrays. Each pod has default four application workers. Real Argo execution/RBAC/version checks are blocked. |
| D-034 | Implementer / provider boundary | Implement GCS content/input and SDK BigQuery/HTTPS Trino clients without making cloud calls by default. Azure hosting remains an option; Azure Blob is not implemented. | D-015 remains catalog/ownership-gated. JWT token/env or approved protected private Trino; GCP identity/billing must be explicitly provided. |
| D-035 | Implementer / evidence | Retain real 10k/100k stage measurements and six synthetic labeled cases, not a human quality study or billion-URL claim. Optional KeyBERT study stays local, uninstalled and revision/license-gated. | D-002/D-009/D-024 selected; observed topic weaknesses recorded. Windows local Iceberg URI compatibility is explicitly handled; lock pins versions, not artifact hashes. |
| D-036 | Implementer / release and data policy | No destructive retention/GC, public ingress or cloud action is automatic. Keep private content out of submission; define owner-approved deletion/backups before release. Supply conditional remaining-effort estimates, not an invented deadline. | D-025/D-026 reconciled in runbook/release/estimate docs. Part 1 public demo and real mandatory-stack evidence remain incomplete. |
| D-037 | Implementer / user-requested failure fix | Separate the default 5 MiB wire limit from a 10 MiB decoded HTML limit, each bounded at 20 MiB; retain the 512 KiB robots budget and bounded decompression. A measured CNN response is 5,750,759 decoded bytes, so the former shared 5 MiB cap rejected valid HTML. | R-019; real CNN success and independent wire/decoded/gzip-bomb regressions. Larger parser memory still needs deployment resource limits; no unbounded fallback. |
| D-038 | Implementer / user-requested failure fix | Preserve known HTTP status, page final URL/content type and query-redacted failure stage/URL/byte context in API/outbox records. Use the existing metadata string map and Iceberg `metadata_json`, avoiding a physical schema change. Distinguish robots access denial from a parsed disallow; cached denials retain context. | FR-003/FR-008/FR-012; API/worker/outbox and real Iceberg tests. Robots-only failure never invents an article final URL; complete attempt history remains future work. |
| D-039 | Implementer / reliability fix | Classify non-200 responses from status/headers without decoding their bodies; accept numeric and HTTP-date Retry-After with the existing 60-second cap. Keep three attempts, origin pacing, user agent, original URLs and no-bypass policy unchanged. | Large error pages no longer mask a 503 as a decoding limit. Original Amazon still returns 503 and REI robots 403; client fixes do not fabricate access or content. |
| D-040 | Implementer / live extraction regression | Read the document head title rather than joining every title element, which included SVG accessibility labels such as Close icon in CNN metadata. Preserve Open Graph fallback. | FR-005; inline-SVG title regression and corrected live CNN title. This does not resolve broader YAKE relevance/boilerplate limitations. |
| D-041 | Implementer / real-site quality findings | Use generic main/article content regions, exclude dialog/hidden/navigation text, preserve repeated structured records through a bounded under-retention fallback, and supplement JSON-LD with microdata or combined identifier/price facts. Separate metadata/paragraph sentences for local topics. | R-020; product wrapper misclassification, lost country records and dialog/cross-boundary topic noise fixed. Emit strategy evidence/warnings and v2 extractor/classifier versions; no host-specific runtime rules or new services. |
| D-042 | Implementer / readiness correction | Do not accept terminal jobs or nonempty body as sufficient crawler-quality evidence. Require selected real-site smoke tests plus content completeness/type/boilerplate checks and an independent held-out study before general quality claims. Retain the cost of quality changes in performance evidence. | 8/11 selected URLs fetched, eight same-HTML comparisons pass; 250/250 country names retained. v2 repeated-template extraction measured 131 records/s versus earlier 171 in separate shared-machine runs, not a controlled causal comparison or production rate. |
| D-043 | Implementer / standards interpretation | Retain the documented conservative robots 401/403 policy for this profile, while explicitly distinguishing it from an actual article denial. RFC 9309 permits access after unavailable robots 4xx; that optional policy is not currently enabled. | No claim that robots 403 proves target-page inaccessibility, no silent URL/identity repair and no bypass. Standards-aligned behavior and stricter operator choices must be reported separately. (Superseded by D-051 per user instruction). |
| D-044 | User-requested architecture refinement | Extend the static baseline with opt-in Playwright only for a successfully fetched, script-backed text-empty shell. Preserve structured errors for 401/403/429/503 and detected challenges; no stealth, realistic-header impersonation or CAPTCHA bypass. | Partially supersedes D-010/D-028 rendering exclusion; R-021/R-022. This is not a promise of arbitrary-site or Amazon access. |
| D-045 | Implementer / preserve tested architecture | Extract `CrawlPipeline` from worker persistence; retain authenticated async job API, aiohttp/lxml/Trafilatura and local YAKE rather than rewrite for httpx/BeautifulSoup names or add a competing synchronous public pipeline. | Same stateless analysis code serves durable workers; FR-001/FR-009/FR-027. Existing jobs/read contracts remain compatible. |
| D-046 | Implementer / browser safety and limits | Fulfill all browser resources through the existing guarded Python fetcher, never continue native requests or fulfill redirects. Deny browser-native egress with a reject-only local endpoint and failing DNS. Fresh sandboxed contexts, no imported profiles/credentials, finite request/decoded/DOM/time limits and restricted browser features. | R-021; actual installed-browser execution and forbidden-resource/redirect/request/DOM regressions. Redirected assets/new navigation are explicitly unsupported; remote CPU/RSS/egress/sandbox validation remains required. |
| D-047 | Implementer / metadata and unified storage | Return bounded JSON-LD, keywords, h1-h3, author/time candidates, breadcrumbs, image alt, links/counts, word count, page-type evidence, fetch method and measured timings. Preserve complete additive fields/weighted topic scores in existing Iceberg metadata JSON; keep physical schema 1. | v3 extraction/classification provenance; API/worker and real six-row Iceberg roundtrip. JSON-LD output budget 32 KiB, 50 sampled links and 1,000 scanned anchors; no claim that declared publication time is independently verified. |
| D-048 | Implementer / SEO ranking and evidence | Weight YAKE candidates by actual metadata location, retain lower-is-better raw and adjusted scores, suppress nested phrase duplicates and evidenced article-publisher suffixes, and permit short uppercase acronyms. Return evidence, not invented confidence/taxonomy accuracy. | R-023; targeted regressions and three same-HTML comparisons. No spaCy/KeyBERT/zero-shot model installed; merchandising fragments/semantic relevance still need held-out human evaluation. |
| D-049 | User additional inputs / observed evidence | Keep the three original PDF URLs and add Amazon/Walmart/Best Buy homepages in a separate six-input manifest. Preserve query identity/canonical candidates; do not assume PDF concatenation or silently replace the Amazon input. | R-022/R-023: CNN and Walmart content plus Best Buy country-selector landing content; two Amazon 503s and REI outcomes remain explicit. GUI product access is not automated extraction. |
| D-050 | Implementer / deployment boundary | Document Cloud Run as an API candidate with external durable stores and an approved worker execution model; retain required remote Kubernetes/Argo integration. Supply a separate optional Chromium worker image definition, not an unverified scale-to-zero background worker claim. | R-024; no account/region/budget/IAM/builder/public-repository destination supplied; image/build/cloud/public/mandatory-engine evidence remains blocked. |
| D-051 | User-requested RFC 9309 robots 4xx policy | Treat all 4xx `robots.txt` responses (including 401/403, excluding 429) as unavailable/allow per RFC 9309 §2.3.1.3 and proceed with the standard crawler fetch of the target URL. | Supersedes D-043's conservative 401/403 robots block. |
| D-052 | User-requested browser escalation for 403/503 assignment URLs | When `browser_fallback=True` and static HTTP returns `403`/`503` at `stage="fetch"` after passing `robots.txt` and public-DNS SSRF checks, escalate to `BrowserRenderer.fetch_page`. Run Playwright headless first (retrieving Amazon 200) and off-screen (`--window-position=-2000,-2000`) when PerimeterX blocks headless on REI, aborting private/non-HTTP(S) routes and heavy media. | All 6/6 URLs (Amazon product, REI article, CNN article, Amazon/Walmart/Best Buy homepages) now extract and publish to local Iceberg (`expanded-samples-20261115T015237Z.json`). |

## 9. Opening questions and assumptions

| ID | Owner / blocking stage | Question and safe planning position |
|---|---|---|
| Q-001 | User / T08-T12 | Which remote cluster/namespace, registry/build system, PostgreSQL, object store and catalog are authorized? Do not use shared resources by assumption. |
| Q-002 | User / T13-T14,T18 | Which Azure/GCP account, GCP project, region, cost cap, IAM and teardown policy are approved? No cloud actions yet. |
| Q-003 | Implementer + owner / T10,T14 | Which pinned catalog/PyIceberg/Trino/BigQuery combination works, including token refresh? Prove it before finalizing connector configuration. |
| Q-004 | User/evaluator / remaining quality scope | Supplied URLs and optional bounded JS-shell rendering are selected in D-044. Are English-first evaluation and free keyphrases acceptable, or is a required taxonomy expected? Do not equate heuristic keyphrases with a trained taxonomy classifier. |
| Q-005 | Evaluator / ingestion contract | Does year-month select source rows or require historical content? Assume source/run context only until clarified. |
| Q-006 | Evaluator / final scale/SLO model | Required ingestion completion window, distinct origins, peak reads, freshness, content-size distribution, retention and deletion obligations? Model variables rather than invent throughput. |
| Q-007 | User/evaluator / submission | Actual deadline, receipt acknowledgment, delivery format and estimation expectations? No email or public upload is authorized by this plan. |
| Q-008 | Owner / T18 | API authentication/access policy and permission to expose the demo publicly? Proposed API-key or platform identity plus limits. |
| Q-009 | Evaluator / quality evaluation | How should unavailable sample URLs and anti-bot pages be scored? Record actual outcomes and use separate deterministic fixtures. |

Q-004's supplied-URL/English-first/free-keyphrase defaults and Q-005's
source-month interpretation are selected POC assumptions under plan approval.
The later architecture request adds opt-in bounded rendering, not unrestricted
browser/network/session automation; D-044 through D-046 record its boundaries.
Evaluator taxonomy, historical-content expectations and final quality criteria
are still unanswered; this is not a claim that the user explicitly answered them.
Other resource/SLO/deadline questions remain stage-gated and outstanding.

## 10. Implemented bounds and evidence

The source-of-truth implementation is `src\crawler_poc`; the physical mapping is
`data-model.md`. Runtime defaults/maximums are documented in `docs\runbook.md`
and validated by `Settings`/`CrawlRequest`. Local verification and limitations
are in `docs\poc-evaluation.md`; `docs\submission-manifest.md` maps all assignment
parts and incomplete deliverables. Tests do not automatically check reviewer boxes.
