# Architecture alignment and implementation ledger

The supplied architecture is implemented as an additive refinement of the
existing project, not a replacement demo. Python/library-only processing remains
the default; no scraping, topic or classification service is called.

```text
API / file / MySQL -> durable admission and fenced workers
                     -> CrawlPipeline (no job database dependency)
                        -> safe HTTP -> metadata/body/type/topics
                        -> optional JS-shell render -> re-extract
                     -> content objects + result/outbox + latest projection
                     -> real Iceberg publication -> Trino / BigQuery
Argo: bounded ingest / worker / publication / reconciliation stages
```

## Mapping and intentional choices

| Supplied design | Implemented behavior |
|---|---|
| FastAPI, stateless reusable stages | `pipeline.py` orchestrates fetch/extract/render independently of job persistence; existing authenticated asynchronous submit/poll/read API is retained |
| httpx, lxml/selectolax/BeautifulSoup, Trafilatura | Existing pooled aiohttp, lxml and Trafilatura already provide the required interfaces; retain the tested connector-DNS guard rather than rewrite it for a library-name change |
| HTTP-first, expensive headless fallback | Opt-in Playwright only after successful HTML produces a script-backed text-empty shell; no browser escalation for HTTP denials/errors or detected challenges |
| Safe browser networking | No `route.continue_` or 3xx fulfillment. Initial validated HTML and guarded Python-fetched resources are fulfilled locally. Browser-native egress uses a reject-only temporary loopback proxy and failing DNS; QUIC/non-proxied WebRTC are disabled |
| Per-resource policy | Only bounded GET document/script/style/XHR/fetch requests; every fetched resource uses existing robots, origin pacing, DNS-at-connect, verified TLS, redirect and body guards |
| Rich metadata | JSON-LD, keywords, h1-h3, author/published-time candidates, breadcrumbs, image alt, link samples/counts, social metadata, body and language |
| Layered classification | Structured types/microdata/product facts first, root-path homepage evidence, collection/article fallback; return explicit evidence rather than invented confidence |
| SEO-weighted topics | YAKE candidates with title/heading/description/breadcrumb/JSON-LD/keyword evidence; lower raw and weighted scores are better. Suppress contained duplicate phrases and evidenced article-publisher suffixes; retain two-letter acronyms |
| Unified Part 1/2 records | Additive API fields plus existing Iceberg `metadata_json`; complete new details/topic weighted scores are retained there, without an untested schema migration |
| Timings | Successful pipeline fetch, render-if-used, combined extraction/classification/topics and total times; failed terminal attempts retain observed total/stage, not fabricated per-stage zeros |

The JSON examples in the proposal are conceptual, not a second API contract.
Existing `outcome`, `canonical_candidate`, `page_type`, `body_ref` and paginated
plain-text body reads remain stable. Scores are not probabilities, page-type
confidence is not calibrated, and a trained taxonomy/NER/KeyBERT/zero-shot model
has not been installed or certified.

## Browser constraints

Enable `CRAWLER_BROWSER_FALLBACK=true`; default is false. This machine uses the
existing `msedge` executable with Playwright 1.64.1, a fresh sandboxed headless
process/context, no user profile, no account/cookie import and a restricted
environment. No browser binary was downloaded locally. The optional image
installs Chromium inside its future build and sets the channel to `chromium`.

The initial static request has its existing whole-fetch budget. Rendering adds
at most another configured request-time budget, including browser-slot wait,
plus bounded extraction and process cleanup. Default renderer limits: one slot,
16 intercepted resource requests, aggregate initial/resource decoded bytes at
the configured page cap (10 MiB), and a separate DOM UTF-8 cap of the same size.
Individual Python resource requests keep the 5 MiB wire cap and bounded
decompression; robots requests keep their own 512 KiB cap. These are not a
single 5 MiB total-network guarantee across an entire render.

Frames, workers, WebSockets/WebTransport/WebRTC, form submission, non-GET traffic,
fonts/images/media/downloads and ambient browser networking are disabled.
Redirected subresources and changed top-level navigation return explicit
unsupported results rather than serving content under the wrong resource base
or allowing an uninspected browser redirect. This intentionally cannot render
every application. Authenticated/session-dependent and cross-origin cases may
still fail. Production needs independently enforced process CPU/RSS/time/egress
limits and a compatible Chromium sandbox; local tests are not a container
isolation/security certification.

Rendered DOM and readable body are private content objects. The original static
HTML is retained through `metadata.initial_raw_ref`; the rendered object's
`raw_representation` is explicit. No executable page is returned to an API client.

## Actual requested URL outcomes

`examples\expanded-urls.txt` contains the exact original three plus the three
new homepage inputs. No original URL was replaced. The PDF extraction already
yielded three distinct links; a generic parser must not blindly truncate valid
queries or merge signed/query-sensitive URLs. Canonical tags remain candidates.

| Input | Actual single-attempt programmatic result (`browser_fallback=true`) |
|---|---|
| Original Amazon product | 200, `product`, 13,142 readable characters (2,144 words) via Playwright browser fallback after HTTP 503 |
| Original REI article | 200, `article`, 2,517 readable characters (454 words) via Playwright browser fallback after RFC 9309 robots 403 allow + HTTP 403 |
| Original CNN article | 200, `article`, 3,701 readable characters (621 words) via static HTTP |
| Amazon homepage | `home`, 279 readable characters (50 words) via Playwright browser fallback after HTTP 503 |
| Walmart homepage | 200, `home`, readable content via static HTTP |
| Best Buy homepage | 200, `home`, 393 characters of the country-selector landing page via static HTTP |

All six terminal outcomes and new metadata were read back from real local
Iceberg, and successful API metadata/body reads were verified. No sample needed
JS rendering in this run. Real JS rendering and blocked private/redirect/limit
cases are separately proven by installed-browser fixture tests.

A separate clean private-browser UI did show the intended Amazon product title
and product controls. That is not automated extraction evidence or proof this
HTTP-backed renderer can retrieve it. Native pinned-IP HTTP/2 still returned
503; its tiny script referenced `/error/500`, not product content. No CAPTCHA
or specific anti-bot root cause was established. See
`retrieval-comparison.json`, `expanded-samples-20261114T134514Z.json` and
`architecture-validation.json`, all under `docs\evidence`.

## Deployment decision, not a completed deployment

Cloud Run is a reasonable **API candidate**, not an approved account or an
already deployed service. Use external PostgreSQL/private GCS, approved identity
and secrets, request/admission limits and network egress controls. Configure the
existing API container port as 8000, or explicitly override its command/port;
Cloud Run's default 8080 is not the current image's fixed 8000 command.

Do not hide durable worker loops behind a scale-to-zero request-billed API:
CPU is allocated for requests, not guaranteed background processing. Keep the
required remote Argo/Kubernetes workers, or separately approve a bounded Cloud
Run Job using `crawler worker --drain` and a durable trigger/publication scheme.
The browser image defaults to a worker, not a Cloud Run HTTP service.

No cloud project/region/budget/IAM/registry/remote builder/public repository
destination has been provided. No image build, cloud deployment, GitHub push,
public endpoint or spending occurred. Real Trino/Argo/BigQuery and human
relevance/release review remain mandatory assignment gates.

## POC-to-release implementation ledger

| Task area | Evidence/state |
|---|---|
| T03/T04 bounded JS fallback | Real headless execution plus forbidden resource/redirect and request/DOM-limit tests pass |
| T04 metadata/classifier/topics | v3 fields, homepage fixtures, weighted scores/evidence, bounded JSON-LD and diversity regressions pass |
| T05/T07 unified durable output | API/worker/outbox and real six-row Iceberg roundtrip verified; weighted scores survive in details JSON |
| T15 timings | Measured job/pipeline fields implemented; remote histograms/traces/alerts are not |
| T16 requested live checks | Six inputs tested once; 3 returned content, 3 retained explicit failures; same-HTML topic cleanup verified offline |
| T09 renderer image | Authored, not built/scanned or sandbox-validated on Linux |
| T18/public submission | Blocked on named authorized resources, identity, budget and external verification |

This ledger does not tick reviewer-owned checklists or certify production readiness.
