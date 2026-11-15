# Research and evidence

Status: original planning research plus implementation observations below.
Measured results are separate in `docs\poc-evaluation.md` and `docs\evidence`.

## Initial planning baseline (historical, before "build it")

- Source PDF: three pages, read using installed pypdf; text and embedded links inspected.
- Target `<repo-root>` does not exist.
- No assignment repository/code/tests were provided. Existing unrelated home-directory projects were not treated as this codebase.
- Python 3.12.10, uv 0.6.13, Specify CLI 0.0.22 and Git are discoverable.
- `specify init --help` exposes `--ai copilot --script ps`; current upstream uses `--integration`.
- No Docker/kubectl/kind/minikube/rustc/cargo/gcloud/bq executables were discovered on PATH. No installations were attempted.
- No dependencies were installed, models downloaded, sample websites crawled, cloud accounts accessed, images built or cluster resources changed.

## Authoritative sources and implications

| ID | Source | Verified finding | Design consequence |
|---|---|---|---|
| R-001 | https://github.github.io/spec-kit/quickstart.html and https://github.com/github/spec-kit | Current SDD flow includes constitution, specify, clarify, plan, checklist, tasks, analyze, implement and converge; integration syntax has evolved. | Pin and inspect the chosen release. Staged manual drafts are not command-run evidence. |
| R-002 | https://docs.aiohttp.org/en/stable/client_quickstart.html and https://docs.aiohttp.org/en/stable/client_advanced.html | ClientSession reuses connections; whole-body reads materialize content; chunked response consumption is supported. | Reuse sessions; enforce finite decoded/wire budgets while streaming. Validate chosen-version resolver behavior separately. |
| R-003 | https://docs.scrapy.org/en/latest/topics/autothrottle.html | Scrapy adjusts per-download-slot delays using observed latency; error responses must not reduce delay; hard per-domain concurrency remains relevant. | Borrow the scheduling principles; Scrapy is a credible alternative to a custom aiohttp pipeline. Library throttling alone is not cross-worker coordination. |
| R-004 | https://trafilatura.readthedocs.io/en/latest/usage-python.html | Main-text extraction has precision/recall tradeoffs and fallback paths; simpler baseline/all-text paths exist. | Benchmark quality and CPU across articles, product pages and sparse HTML. Metadata extraction must not depend solely on article text heuristics. |
| R-005 | https://raw.githubusercontent.com/LIAAD/yake/master/README.md | YAKE is a local, single-document unsupervised keyword extractor requiring no training corpus; lower scores mean greater relevance. | Appropriate explainable baseline. Preserve scoring semantics; do not report the score as probability or fixed-taxonomy accuracy. |
| R-006 | https://maartengr.github.io/KeyBERT/ | KeyBERT ranks candidate phrases using document/phrase embeddings and similarity; batching can help. | Optional local pretrained comparison, not a required hosted service. Measure model artifact/loading/inference costs and validate licenses. |
| R-007 | https://py.iceberg.apache.org/api/ and https://py.iceberg.apache.org/configuration/ | PyIceberg is catalog-centric, writes Arrow data, supports append/overwrite and commit retries; fast appends can grow metadata. | A real catalog and commit protocol are required. Batch rows; plan metadata maintenance and test replay semantics rather than assume append deduplication. |
| R-008 | https://trino.io/docs/current/connector/iceberg.html | Trino supports Iceberg v1/v2, with v3 experimental; requires supported object storage and a catalog such as REST. | Prefer v2/Parquet and explicitly configure both catalog and filesystem. |
| R-009 | https://docs.cloud.google.com/lakehouse/docs/set-up-lakehouse-iceberg-rest-catalog | Google's catalog endpoint is a shared Iceberg REST interface for GCS and BigQuery interoperability; current docs describe v2 support, region/identity rules and engine-specific authentication. | Strong GCP-aligned candidate, but not proof that arbitrary PyIceberg/stock Kubernetes Trino builds work unchanged. |
| R-010 | https://docs.cloud.google.com/bigquery/docs/biglake-iceberg-tables-in-bigquery and https://docs.cloud.google.com/bigquery/docs/iceberg-external-tables | BigQuery-managed tables own their writes/files; external modification can cause data loss. Metadata-file external tables are read-only and need explicit metadata URI refresh, and are no longer the default recommendation for most cases. | Choose ownership/catalog model explicitly. Do not mix external PyIceberg writes with BigQuery-managed file ownership. A snapshot-pinned external-table fallback must document refresh/freshness limitations. |
| R-011 | https://argo-workflows.readthedocs.io/en/latest/walk-through/dag/ and https://argo-workflows.readthedocs.io/en/latest/synchronization/ | Argo DAGs support dependencies; default fail-fast stops scheduling new tasks; workflow/template semaphores/mutexes control concurrency; controller-local and database-backed lock scopes differ. | Use bounded manifests, explicit failure policy and appropriate lock scope. Argo limits are not per-origin crawl politeness controls. |
| R-012 | https://www.rfc-editor.org/rfc/rfc9309.html | Robots Exclusion Protocol specifies rule matching, error handling and caching; robots is not authorization. | Adopt a standards-aware parser/policy and test redirects, origin scope, caching and failures. Also honor actual access controls. |
| R-013 | https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html | User-controlled fetches need application/network defenses, robust IP/domain validation and redirect handling. | Validate selected DNS addresses at connection time, manually guard redirects, and enforce remote egress policy. |
| R-014 | https://commoncrawl.org/overview | Common Crawl demonstrates an existing petabyte-scale, regularly collected web corpus. | Useful reference for separating collection, immutable stored content and downstream analytics. Do not replace the required crawler with an external crawl corpus/service. |
| R-015 | Local `<user-path>` and `guide\stack-to-checklist-map.md` | Requirements-quality and implementation-verification checklists are different; the kit has core/data checks but no dedicated Python-crawler/Argo/Iceberg standards set. | Keep project acceptance checks distinct from reusable technology standards. Any new reusable technology checklist needs the kit's Route C process, not an invented certification. |

Google documentation currently redirects older BigLake URLs to Lakehouse catalog terminology. Preserve resolved source URLs and revalidate versions/features when implementing. Preview features must not become hidden baseline dependencies.

## How existing approaches work

1. **Polite crawling:** mature crawlers separate request admission, host/origin pacing and global resource bounds. Async I/O hides network waits; it does not permit unbounded concurrency or overcome the target website's allowed rate.
2. **Extraction:** parse structured/metadata fields independently, then identify readable content. An article extractor alone can miss product details or classify navigation as content.
3. **Topics:** per-document statistical keyphrases are inexpensive and explainable. Embeddings can improve semantic phrase selection but introduce artifact size, CPU/memory, cold-start and licensing tradeoffs.
4. **Lakehouse analytics:** Parquet contains data; Iceberg adds cataloged tables, schema/partition metadata, snapshots and commit semantics. An object full of Parquet files is not automatically an Iceberg table.
5. **Workflow orchestration:** Argo coordinates coarse jobs and artifacts. A worker consumes many URL records from a bounded shard. Backpressure must span queue, fetch, parse, storage and publication.
6. **Serving:** point lookups and API request admission need an operational projection/cache. Columnar analytics engines serve batch/ad-hoc reporting, not every interactive result request.

These are architectural recommendations, not claims that this project already implements them.

## Alternatives and hypotheses to test

| Choice | Preferred POC hypothesis | Alternative / reason to revisit |
|---|---|---|
| Fetch engine | aiohttp with explicit guards and host-aware scheduler | Scrapy if its facilities reduce code without weakening network safety/integration clarity |
| HTML parsing | selectolax or lxml for metadata; Trafilatura for body | One parser only if measured extraction coverage and simplicity justify it |
| Topics | YAKE + weighted metadata evidence and deterministic cleanup | Local pretrained KeyBERT-style pipeline if quality gains justify CPU/RSS |
| Language | Python plus native libraries | Rust extension/worker only for a proven CPU bottleneck, not network/site limits |
| Operational POC store | Remote PostgreSQL; SQLite/files for infrastructure-free core tests | Provider-native production key/value store after workload/partition validation |
| Analytical table | Externally owned v2/Parquet in a REST catalog | BigQuery-managed table only with a redesigned BigQuery-owned write path |
| BigQuery integration | Read the same externally owned publication through a compatible supported catalog | Explicit snapshot-metadata registration or a materialized projection with declared lag; do not silently substitute |
| Orchestration | Remote Argo with bounded shard manifests | Direct CLI execution only for core debugging, not Argo completion evidence |

## Required compatibility experiment

- Pin Python packages, Trino image, Iceberg format/catalog and Argo version.
- Use approved remote identity/storage; create a tiny isolated fixture table.
- Python writes a batch with nulls, Unicode, timestamps and nested topics.
- Trino reads/reconciles; verify schema mapping and predicate pruning.
- On approved GCP access, BigQuery reads the intended publication and reconciles normalized values.
- Exercise token renewal, a second publication, failed/ambiguous commit, restart and replay.
- Confirm maintenance ownership and snapshot retention before enabling compaction/expiration.

Important caveats from R-009: Google documents credential vending support for Trino 481+ and specific managed-runtime compatibility; these statements are not interchangeable with support in any stock Trino container. Current catalog docs also impose metadata/format/region limitations. Validate the selected combination instead of copying managed-service examples into Kubernetes and assuming equivalence.

## Uncertainty and access limits

At the planning baseline no measured throughput/quality or integration evidence
existed. The Scrapy broad-crawl page was unavailable through the fetch tool and
its guessed raw source returned 404; only the successfully read AutoThrottle
documentation is relied upon.

## Implementation observations

| ID | Evidence | Finding and consequence |
|---|---|---|
| R-016 | `.specify\bootstrap.json`, pinned upstream `templates\commands\analyze.md` | Global Specify 0.0.22 could not consume current assets; isolated modern package fetch failed TLS. Pinned official source/scripts plus thin prompts are present. Actual prerequisite execution and a manual agent semantic analysis are distinguished from unexecuted slash commands. |
| R-017 | Installed PyIceberg 0.11.1 `io\pyarrow.py`, `lakehouse.py`, real replay test | Canonical Windows file URI parsing passes `/C:/` to Arrow and fails. The local adapter uses the supported-by-this-parser `file://C:/...` shape only on Windows; remote object URIs are unchanged. Real local v2 writes/reads and crash-before-ack replay then passed. |
| R-018 | Raw benchmark/quality/original-URL JSON under `docs\evidence` | Parser throughput does not represent full NLP throughput; streamed 100k aliases have stable sampled RSS but persistent disk growth. Synthetic topics show redundancy/boundary artifacts. Original REI was robots-disallowed, CNN exceeded decoded cap and Amazon returned a transient outcome; no bypass or fabricated extraction. |
| R-019 | `url-diagnosis-20261114T093606Z.json`, `url-fix-20261114T094736Z-415670.json`, `url-fix-validation.json` in `docs\evidence` | CNN serves 200 gzip HTML (1,198,821 compressed / 5,750,759 decoded bytes); a 10 MiB decoded budget with unchanged 5 MiB wire limit succeeds. A global title XPath also included an SVG label. Failed-job response context was discarded, obscuring Amazon 503 and REI robots 403. Separate bounded budgets, head-only title extraction and terminal error metadata fix these implementation defects; external denials remain. Full suite: 66 passed, one cloud skip; project checks pass. |
| R-020 | RFC 9309 sections 1/2.3.1.3; https://trafilatura.readthedocs.io/en/latest/corefunctions.html; `real-site-baseline-20261114T125733Z.json`, `real-site-content-improvements.json`, `generic-content-validation.json`, `extract-v2-10k.json` in `docs\evidence` | A small guarded live corpus yielded stored content for 8/11 URLs but exposed quality defects: an article extractor returned a nonempty 350-character introduction instead of a country directory, global headings polluted topics, and a product lacked JSON-LD. Same saved HTML now retains all 250 country names in 18,089 characters, classifies the product correctly and removes the identified CNN topic noise. A precision preference is not a completeness guarantee. Robots 4xx permission is optional under RFC; the configured stricter policy is not a measured article denial. Current tests 70 pass/one cloud skip; v2 synthetic extraction 131 records/s, not a web-scale capacity claim. |
| R-021 | https://playwright.dev/python/docs/network and installed Playwright 1.64.1; `tests\test_rendering.py` | Playwright routing runs before browser networking, but a continued/3xx-fulfilled redirect is followed without another route call. A preflight DNS check is insufficient. Fulfill only guarded Python-fetched final resources, never continue native traffic/redirects; deny native egress, restrict features and prove actual JS plus forbidden-resource/redirect/limit behavior. Browser library installed only in the project; existing Edge executable used without a browser download. |
| R-022 | `docs\evidence\required-amazon-probe-20261114T131605Z.json`, `retrieval-comparison.json`; bounded native HTTP/2 diagnostic and fresh private-browser observation | Exact Amazon default/Accept/canonical diagnostics returned 503; native pinned-IP HTTP/2 also returned a 316-byte JavaScript/noscript error-page redirect referencing `/error/500`, without product content. A later private Edge UI exposed intended product title/controls, not programmatic extraction. Neither CAPTCHA nor a specific anti-bot root cause is proven. Rendering cannot turn an HTTP 503 error script into product metadata. |
| R-023 | `docs\evidence\expanded-samples-20261114T134514Z.json`, `architecture-validation.json` | Six fresh jobs produced CNN article, Walmart homepage and Best Buy international country selector; Amazon product/home returned 503 and REI stopped at robots 403. All six outcomes/new details roundtripped real local Iceberg. Metadata weighting initially amplified nested phrases/publisher terms; same saved HTML verifies subsequent generic containment/publisher cleanup without more requests. Final 89 tests pass/one cloud skip; independent relevance and v3 performance remain unmeasured. |
| R-024 | https://docs.cloud.google.com/run/docs/configuring/billing-settings and https://docs.cloud.google.com/run/docs/container-contract | Default request-based CPU does not guarantee idle background work; jobs must terminate, and services must listen on their configured ingress port (8080 default, configurable). Keep durable stores outside ephemeral service files; separately choose worker/trigger lifecycle. Existing API image serves 8000, optional browser image runs a worker. Neither definition is proof of Cloud Run deployment or Linux sandbox compatibility. |
| R-025 | Existing `api.py`, `storage.py`, `pyproject.toml`; confirmed PRODUCT/DESIGN context; `tests\test_ui.py`, `tests\test_ui_browser.py` | Existing durable async jobs already provide the UI lifecycle; no frontend framework is necessary. Latest-document reads are generation-mutable, so body viewing needs the exact successful job reference. Browser tests exposed a heading role override and a reset-button ID shadowing `form.reset`; both were fixed. Python slices Unicode code points, so JS pagination counts `Array.from(text).length`. Package-data must be checked in a built wheel, not just the editable source checkout. |
| R-026 | `CrawlRequest`, `Store.submit`, API request quota and real browser batch tests | The API already accepts up to 100 URLs and returns identifiers in input order; normalized duplicates share durable jobs. Commas can be valid URL data, so use whitespace delimiters. Per-job four-second polling across 100 jobs would exceed the shared default 60-request/minute quota; sequential 1.5-second-spaced polling limits automatic batch polls to about 40/minute. Row selection also needs a view-version guard so late body responses cannot append to another result. No new batch endpoint or storage model is necessary. |

Selected libraries and package versions were installed in an isolated `.venv`,
not globally. Local SQLite/files and controlled loopback HTTP servers were used;
no local containers/Kubernetes or cloud services were installed/deployed.
No pretrained model downloaded. Remote catalog/engine compatibility and cloud
cost/public endpoint evidence still do not exist; keep R-009/R-010 uncertainty.
