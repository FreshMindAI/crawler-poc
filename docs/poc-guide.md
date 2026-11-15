# POC guide and assignment details

Run the commands below from the repository root.

Python-first implementation of the BrightEdge assignment: asynchronous URL jobs,
safe HTTP fetching, HTML metadata/body extraction, explainable local page types
and YAKE topics, streaming input, durable state, and real Apache Iceberg publication.
No managed crawling, extraction, classification, or LLM service is used.

**Status:** the local application and Iceberg recovery tests work. Trino/BigQuery
clients, Kubernetes profiles and a bounded Argo DAG are implemented but **not
remotely verified or deployed**. A public Azure/GCP demo still requires authorized
resources. This is not a completed cloud submission or a billion-URL demonstration.

Latest requested six-input check (`docs\evidence\expanded-samples-20261115T015237Z.json`):
**all 6 of 6 URLs (including all 3 original assignment URLs) extracted and published
to local Iceberg** with `CRAWLER_BROWSER_FALLBACK=true`:
- **Amazon product (`B009GQ034C`)**: `200`, `product`, 13,142 chars / 2,144 words (`fetch_method=headless`)
- **REI blog article**: `200`, `article`, 2,517 chars / 454 words (`fetch_method=headless`)
- **CNN tech article**: `200`, `article`, 3,701 chars / 621 words (`fetch_method=http`)
- **Amazon homepage**: `home`, 279 chars / 50 words (`fetch_method=headless`)
- **Walmart homepage**: `200`, `home`, 54–1,813 chars (`fetch_method=http`)
- **Best Buy homepage**: `200`, `home`, 393 chars / 60 words (`fetch_method=http`, country-selector landing page)

The reusable pipeline now includes opt-in, guarded Playwright JS-shell rendering,
bounded structured metadata, homepage typing, location-weighted/deduplicated
topics and timings. See `docs\architecture-alignment.md` and the actual outcomes
in `docs\poc-evaluation.md`; this does not guarantee protected-site access.

## Run locally (Python 3.12)

No containers, Kubernetes, Java, or local infrastructure services are required.

```powershell
Set-Location 'C:\path\to\crawler-poc'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
$env:CRAWLER_API_KEY = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))")
.\.venv\Scripts\crawler.exe init-db
.\.venv\Scripts\crawler.exe serve
```

In another terminal, with the **same project directory and database/object
configuration**, start workers:

```powershell
.\.venv\Scripts\crawler.exe worker
```

Requests need the same API key configured in the API process. Keep it in an
approved local secret mechanism; do not commit it. The API refuses an empty or
short key. `.env.example` documents variables; it is **not automatically loaded**.

```powershell
$headers = @{'X-API-Key' = $env:CRAWLER_API_KEY; 'Idempotency-Key' = 'example-1'}
$job = Invoke-RestMethod http://127.0.0.1:8000/v1/crawls -Method Post `
  -Headers $headers -ContentType application/json `
  -Body '{"url":"https://example.com/","top_k":5}'
Invoke-RestMethod ("http://127.0.0.1:8000/v1/crawls/" + $job.job_ids[0]) -Headers $headers
```

Jobs are asynchronous. Poll until `status` is `terminal`; inspect `result.outcome`.
Use the returned `url_id` with `GET /v1/documents/{url_id}` or
`GET /v1/documents/{url_id}/content?offset=0&limit=16000`. Only the latest successful
generation updates this projection. An explicit new `generation` requests a recrawl.
`POST /v1/crawls/{job_id}/cancel` fences an in-flight worker.

Page limits default to **5 MiB downloaded / 10 MiB decoded**. Configure
`CRAWLER_MAX_WIRE_BYTES` and `CRAWLER_MAX_BYTES` respectively; each has a
20 MiB maximum. Robots remains capped at 512 KiB. Existing explicit environment
values override these defaults.

Failed results retain observed `http_status`, response `content_type` and page
`final_url` when known. `metadata.failure_stage` distinguishes robots/fetch/
extraction failures, and `metadata.failure_url` removes query/fragment values.
Robots 4xx responses other than 429 are treated as unavailable/allow under the
selected RFC 9309 policy. Parsed disallow rules, robots 429 and server/network
failures still stop the target request.

## Optional JavaScript rendering

The HTTP path remains the default. For an already installed Edge runtime on this
Windows machine:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-browser-lock.txt
$env:CRAWLER_BROWSER_FALLBACK = 'true'
$env:CRAWLER_BROWSER_CHANNEL = 'msedge'
.\.venv\Scripts\crawler.exe worker --drain
```

The current implementation has two distinct browser paths:

- Successful JS shells use guarded Python resource fulfillment with native
  browser egress denied and bounded resource requests/bytes.
- Target HTTP 403/503 can invoke native browser navigation. This path first
  tries headless mode and can retry in a headed, off-screen window. It uses
  different networking and does not provide the first path's socket-level DNS,
  redirect or resource-budget guarantees. The recorded REI success therefore
  must not be presented as proof of headless-only cloud operation.

Both paths are opt-in. The native path requires further isolation and security
validation before public deployment. The optional `deploy\Dockerfile.browser`
is authored but **not built or deployed**; headed fallback also needs an
appropriate display environment on Linux. Local success does not establish
container compatibility or reliable access to every target.

## Operator CLI

```powershell
.\.venv\Scripts\crawler.exe ingest --input examples\assignment-urls.txt `
  --run-id sample-run-1 --month 2026-11
.\.venv\Scripts\crawler.exe worker --drain
.\.venv\Scripts\crawler.exe publish --local var\iceberg
.\.venv\Scripts\crawler.exe reconcile
.\.venv\Scripts\crawler.exe evaluate --output docs\evidence\quality.json
.\.venv\Scripts\crawler.exe benchmark --records 100000 --mode ingest `
  --output docs\evidence\ingest-100k.json
.\.venv\Scripts\python.exe benchmarks\stages.py --mode api --records 10000 `
  --output docs\evidence\api-10k.json
```

`--month` is source/reporting context, **not historical content retrieval**.
`--drain` covers the configured whole queue, including delayed retries and active
jobs. Use an isolated batch control database for the Argo profile. An ingested
shard must fit admission capacity; a capacity failure resumes with the same run
after draining/publication, not a new identity.

MySQL uses `ingest-mysql --help`: credentials come only from the named DSN
environment variable, with a read-only database account, positive monotonic
integer ID and immutable UTC source rows. File input also accepts `gs://` operator
URIs with explicit GCP configuration; it is not exposed as a public API.

`publish` without `--local` uses the named PyIceberg catalog from its standard
configuration. Use a single publication/maintenance owner. `trino-report` and
`bigquery-report` issue real parameterized queries; they do not emulate either
engine. Remote setup, authorization, table visibility and identity are described
in `docs\remote-integration.md`.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests benchmarks
.\.venv\Scripts\python.exe -m ruff format --check src tests benchmarks
.\.venv\Scripts\python.exe -m mypy src benchmarks
```

Cloud tests are skipped unless `CRAWLER_RUN_CLOUD_TESTS=1` is deliberately set
with approved endpoints and expected publication counts. Do not enable them
against an existing organizational account by assumption.
With the optional library and browser installed, set
`CRAWLER_RUN_BROWSER_TESTS=1` before pytest to execute real headless JS, private
destination/redirect and size/request-limit tests. The retained full result is
**91 passed / one authorized-cloud skip**, with these browser tests enabled.
Passing tests do not certify the native browser path's network isolation.

## Specifications and assignment evidence

| Artifact | Contents |
|---|---|
| `specs\001-crawler-poc\spec.md` | Requirements, decisions, open questions, constraints |
| `specs\001-crawler-poc\research.md` | Existing approaches, official sources, implementation findings |
| `specs\001-crawler-poc\plan.md`, `data-model.md`, `tasks.md` | Architecture, schema, dependency plan and status |
| `docs\speckit-analysis.md` | Pinned Spec Kit fallback, semantic consistency findings and limitations |
| `docs\poc-evaluation.md`, `docs\evidence\` | Actual tests, quality and 10k/100k measurements; original URL outcomes |
| `docs\scale-design.md` | Billion-URL architecture, read scaling, cost model and proposed SLOs |
| `docs\remote-integration.md`, `docs\runbook.md` | Remote gates, identity, recovery and retention |
| `docs\release-plan.md`, `docs\implementation-estimate.md` | POC-to-release work, blockers, conditional effort estimates |
| `docs\nlp-backup.md`, `docs\ai-usage.md` | Local pretrained alternative, AI/tool/service/license disclosure |
| `docs\submission-manifest.md` | Assignment coverage and explicit incomplete deliverables |

Spec Kit upstream templates/scripts are pinned in `.specify`; the obsolete global
CLI was not modified. See `.specify\bootstrap.json`. No claim is made that a
modern slash-command integration or a complete automatic CLI lifecycle ran.
Reviewer checklist boxes are deliberately untouched.
