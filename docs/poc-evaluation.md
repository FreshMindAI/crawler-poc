# POC evidence and limitations

## Executed locally

Python 3.12.10, Windows 11 build 26300, isolated project environment; package
versions are in `requirements-lock.txt`. These measurements use a shared machine,
one run per case, no controlled CPU isolation and no external network load.
`docs\evidence\*.json` contains the unrounded observations.

| Workload | Records | Elapsed s | Records/s | Sampled peak RSS MiB |
|---|---:|---:|---:|---:|
| lxml parse/title microbenchmark | 10,000 | 0.538 | 18,587 | 87.4 |
| lxml parse/title microbenchmark | 100,000 | 4.870 | 20,532 | 87.0 |
| Full metadata/body/page type/YAKE extraction | 10,000 | 58.538 | 171 | 88.3 |
| Full extraction/topic v2 after real-content fixes | 10,000 | 76.337 | 131 | 88.6 |
| Streamed file admission/accounting, SQLite | 10,000 | 6.426 | 1,556 | 91.3 |
| Streamed file admission/accounting, SQLite | 100,000 | 78.917 | 1,267 | 91.5 |

Parse/extract repeat a single small synthetic product template. Their latency
samples are systematic samples, not independent end-to-end URL latencies.
Ingestion uses 1,000 distinct URLs, duplicates, and an invalid row every 97
records: the 100k case reconciled **1,000 admitted + 97,969 duplicate + 1,031
rejected = 100,000**. The disk-backed lineage grows with records; no proportional
in-memory URL set is used. Sampled RSS is not a native-allocation peak guarantee.
These are baseline measurements; final release should repeat them after all
storage changes on a declared deployment resource profile.

The first extraction row is the earlier v1 baseline; the v2 row is retained in
`extract-v2-10k.json` after generic content-quality fixes. Both repeat the same
small fixture, but are separate shared-machine runs, not an isolated causal
comparison. Do not assume v1 throughput still applies or extrapolate 131/s to
distinct real-world pages. Profile quality/CPU tradeoffs before considering Rust.
These are historical v1/v2 measurements. V3 metadata/ranking and the optional
browser path have not been benchmarked; no current v3 throughput is claimed.

The 10k extraction result includes local NLP and is much slower than parsing
alone. This identifies extraction/topic work for profiling; it does not establish
that a Rust rewrite is warranted. Async workers primarily hide network waiting.
There was **no 100k live crawl**, sustained public API load, remote database
benchmark, cloud price measurement or verified billion-URL throughput.

Additional stage workloads in `benchmarks\stages.py` were executed, each with
10,000 records and zero errors:

| Workload | Elapsed s | Records/s | Sampled request p95 ms |
|---|---:|---:|---:|
| Raw pooled loopback HTTP, eight clients, 631-byte fixture | 3.174 | 3,151 | 4.718 |
| SQLite jobs/outbox plus real local Iceberg, ten 1k-row publications | 102.022 | 98.0 | Not sampled |
| Authenticated real TCP API, warm single metadata key, eight clients | 113.336 | 88.2 | 144.223 |

These are separate stage tests, not one end-to-end rate. The API sample is below
the provisional 250 ms target **only for this small warm local scenario**, not
proof of an SLO or large distinct-key/read workload. Stage RSS is measured only
before/after (not peak); raw JSON says so. All controlled servers and temporary
catalog engines were closed. An initial storage run failed temporary cleanup
because the local catalog pool remained open; explicit disposal fixed it and the
complete workload was rerun successfully.

## Quality

The historical `quality.json` baseline evaluates six synthetic product/article/category/service/French/
sparse fixtures with Copilot-authored labels. Title exact match and page-type
macro-F1 are 1.0 on this deliberately tiny regression set. They are **not**
independent human annotations or generalization estimates.

Topic term-overlap fractions are 0.8/1.0/1.0/1.0 on the four English fixtures.
Some phrases are redundant or cross paragraph boundaries. This lexical proxy is
not human precision@k or nDCG. French topics abstain based on declared language;
language is metadata evidence, not a reliable language detector. Unknown language
currently uses the English baseline. Build a human-reviewed, held-out diverse
corpus before claiming production classification/relevance quality.

## Original assignment URLs

The exact three unique links were extracted from the supplied PDF into
`examples\assignment-urls.txt`; no links were repaired or silently substituted.
One bounded attempt per job used the real safe fetcher, workers, operational
store and a real local Iceberg commit. `assignment-samples.json` records:

| Sample | Actual outcome |
|---|---|
| Amazon toaster | `retry_exhausted / transient_http_status` |
| REI outdoors | `robots_disallowed` |
| CNN technology | `too_large / decoded_size_limit` |

No successful extraction is invented for these pages, and no policy bypass was
attempted. Failure records were published: three terminal jobs, zero unpublished
events. This is **local Iceberg evidence**, not Trino/BigQuery or cloud-demo
evidence. The report's local metadata URI is a development artifact, not a
portable public download.

A separate real-network `https://example.com/` API/worker smoke attempt also
terminated conservatively with `robots_unavailable / robots_network_or_timeout`
(`live-example.json`). No body read or successful live extraction is claimed for
that attempt. Positive extraction/content-read evidence is from controlled
fixtures; external-site accessibility remains an environment/target dependency.

### Requested fresh retest

At 2026-11-14 09:32 UTC, the exact three assignment URLs were submitted through
the authenticated API with a new generation and verified fresh queued jobs.
Default robots/SSRF rules, 5 MiB wire/decoded cap, 20-second fetch timeout,
one-second origin gap and three-attempt maximum were unchanged.

All three jobs reached terminal state in 10.959 seconds; **0/3 extracted**.
Amazon redirected to HTTPS and returned HTTP 503 on each of three attempts.
REI's robots endpoint returned HTTP 403, so the conservative policy refused the
page without fetching it. CNN's decoded page exceeded the 5 MiB limit.

Timestamped outcomes, attempt counts, job IDs and sanitized request trace:
`docs\evidence\url-retest-20261114T093218Z-29578a.json`. No URLs were substituted,
protection bypassed, limits loosened or cached terminal results reused.

### Failure-stage diagnosis

This subsection records the pre-fix state; the follow-up below records current
behavior and verified results.

A separate bounded diagnostic fetch per original URL at 2026-11-14 09:36 UTC
recorded response headers and wire byte counts without changing application
code, robots policy, user agent or size limits. Evidence:
`docs\evidence\url-diagnosis-20261114T093606Z.json`.

| Sample | Confirmed failing stage | Code location and interpretation |
|---|---|---|
| Amazon | HTTP response handling after HTTP-to-HTTPS redirect | `SafeFetcher.fetch`: HTTPS product request returned 503, marked retryable. The prior worker run exhausted three attempts. A 503 alone does not establish CAPTCHA or anti-bot blocking. |
| REI | Robots authorization, before requesting the article | `SafeFetcher._robots_allowed`: robots endpoint returned 403 with an `Access Denied` title; our conservative 401/403 policy denied the page. No parsed robots rule or article-level response was observed. |
| CNN | Bounded gzip decompression | `SafeFetcher._request`: robots succeeded and article returned 200 HTML with gzip encoding. Advertised compressed length was 1,198,821 bytes; after reading 1,066,596 wire bytes, decoded output reached the configured 5 MiB guard. Transfer stopped there, so total decoded page size and extraction quality were not yet known. |

All three stopped in `fetcher.fetch`, before the worker invoked metadata/body/NLP
extraction. CNN was a configured resource-limit
failure, unlike the upstream error responses for Amazon and REI. A higher bounded
CNN allowance had not yet been applied or shown to produce a successful
extraction at this diagnostic stage.

The original API failure records had null HTTP status/final URL because
`FetchError` carried no response context and the worker's failure branch stored
only `outcome` and `reason`. This was an observability limitation, not evidence
that no HTTP response arrived. The diagnostic trace supplied the observed
statuses; the subsequent fix below preserves context in application results.

Focused verification: `tests\test_fetching.py` and
`tests\test_http_transport.py`: **15 passed in 2.14 seconds**, covering status
mapping, robots, redirects, guarded DNS, gzip limits and timeout behavior.

### User-requested fixes and end-to-end verification

The decoded default is now 10 MiB with the original 5 MiB wire cap retained;
both settings have a 20 MiB maximum. Robots remains limited to 512 KiB.
This accommodates measured valid HTML, not an unlimited retry/rendering fallback.
Non-200 bodies are not decoded, HTTP-date Retry-After is supported within the
existing 60-second delay cap, and robots 401/403 remains a conservative denial.
The new `robots_access_denied` reason distinguishes that response from parsed
disallow rules. No original URL, crawler identity or protection policy changed.

Failure status/content type, known page final URL and redacted stage/URL/byte
context now survive API/worker/outbox/real Iceberg publication without changing
the physical schema. Head-only document title extraction excludes SVG icon
labels that contaminated the first successful CNN sizing probe.

`docs\evidence\url-fix-20261114T094736Z-415670.json` records a fresh authenticated
**real loopback TCP API**, real guarded target HTTP, durable workers and actual
local Iceberg publication. Worker elapsed: 10.828 seconds.

| Original sample | Result after fixes |
|---|---|
| Amazon | Still HTTP 503 after three attempts; status 503, final HTTPS URL and fetch-stage context retained. Upstream availability/access is not fixed. |
| REI | Still robots HTTP 403, one attempt, `robots_access_denied`; robots-stage context retained, article not fetched and page final URL null. |
| CNN | **Success**, HTTP 200; 5,750,759 decoded bytes, 3,701 readable characters, article classification and five YAKE topics. Correct title excludes Close icon. Latest projection and bounded body read verified. |

**1/3 successfully extracted**; all three outcomes were published and read back
from real local Iceberg with matching HTTP/error metadata. The temporary API was
verified responsive and stopped. No public deployment or remote engine evidence
is implied. CNN's YAKE output still contains boilerplate/boundary noise; five
returned topics are not proof of independently scored relevance.

## Real-site coverage and content readiness

`real-site-baseline-20261114T125733Z.json` records a single guarded attempt per
URL on eleven deliberately selected static pages, using durable workers and
verified stored bodies: **8/11 extracted** in 6.671 seconds. Successes were CNN,
Python.org, Python asyncio documentation, RFC 9309, a Books to Scrape product,
Quotes to Scrape, a Scrape This Site directory and HTTPBin HTML. Amazon returned
503; REI and Wikipedia stopped at robots 403 under the configured conservative
policy. This includes purpose-built practice sites; it is not a random
web-success estimate, load test or claim of 8/11 fully correct classifications.

Inspection of those successful bodies exposed real implementation defects.
`real-site-content-improvements.json` compares new extraction on **identical
saved HTML**, without additional requests:

| Observed problem | Verified v2 correction |
|---|---|
| Product wrapped in article, no JSON-LD | Classified as product using generic identifier-plus-price facts; microdata support also added and regression-tested |
| Directory returned only a 350-character introduction | Bounded repeated-record fallback returns 18,089 characters; **all 250 country names** present |
| CNN dialog headings and joined text polluted topics | Semantic content scoping, dialog/hidden pruning and sentence boundaries remove the observed download/cross-boundary phrases; current topics include tech industry workers and Google |

Versioned results expose content scope/body strategy/product evidence; fallback
is reported rather than silently asserted equivalent to precise article text.
All eight saved-page comparisons passed their explicit checks, but only selected
properties were checked: this is not independent annotation, recall/precision
for every field, or a general relevance score. Brand terms/redundancy and sparse
page evidence still need a held-out human study.

Correction to earlier access wording: robots 403 is **not proof the article
denies access**. RFC 9309 section 2.3.1.3 permits access after unavailable 4xx;
this application's stricter 401/403-deny profile is intentional and unchanged.
Actual parsed disallow rules and actual target-page 401/403 are separate cases.

Before calling the assignment crawler ready: obtain a diverse held-out corpus
with expected content/type/topic judgments and agreed thresholds, verify useful
coverage rather than only terminal counts, exercise recovery/fair scheduling
under a realistic host mix, then complete authorized remote/public integration.
The later architecture request enabled the optional, bounded JS-shell rendering
profile below. It is not an automatic response to denied pages or a way to
guarantee protected-site access.

## User architecture and expanded-input verification

`expanded-samples-20261114T134514Z.json` records six fresh single-attempt jobs:
CNN (3,701 readable characters, article), Walmart (1,813, home), and Best Buy
(393, home) succeeded. Best Buy returned its international country-selector
landing page, not the US retail catalog. Amazon product/home both returned 503.
REI remained a robots 403 policy stop; its article was not requested. No input
was silently changed and no denial was escalated to a browser.

Authenticated in-process API admission/result/body reads, real target HTTP,
durable workers and six real local Iceberg rows were verified, including
additive metadata/topic details and error/timing context. This run is not an
external/TCP API or a remote deployment test. None of these six inputs required
browser rendering. Separate tests execute actual JavaScript in the existing
headless Edge runtime and exercise private destinations/redirects plus resource
and DOM budgets.

The first v3 weighting amplified nested keywords and publisher names. The
offline comparison in `architecture-validation.json` uses the same three saved
HTML objects: title/body/type remain unchanged while containment duplicates and
the evidenced CNN publisher suffix are removed. CNN topics include Google, tech
workers/industry and code. Merchandising fragments, brand bias and semantic
redundancy remain; this is not independent precision@k, a trained taxonomy or a
claim that every returned phrase is relevant.

`retrieval-comparison.json` records the separate private-browser versus HTTP
observation. Normal-browser product controls do not establish automated
retrieval. Native HTTP/2 also returned 503, and its script points to an error
page; no CAPTCHA or specific anti-bot root cause is asserted.

## Test evidence

Current local verification: **89 passed, 1 intentionally skipped cloud test**,
with `CRAWLER_RUN_BROWSER_TESTS=1` and the installed browser runtime.
Ruff check/format, mypy (application and benchmarks), and `pip check` all pass;
the latest commands, outputs, source hashes and offline comparison are retained
in `docs\evidence\architecture-validation.json`. Earlier v2 test/synthetic
evidence remains in `generic-content-validation.json`; it is historical.
The original 52-pass baseline remains in `docs\evidence\local-validation.json`.
Fourteen added regression cases cover contextual status/robots cache handling,
HTTP-date retries, independent size bounds, error-body status precedence,
worker/API/outbox/Iceberg preservation and SVG title exclusion.
Project checks use the README's `src tests benchmarks` scope. A broader
`ruff check .` also encounters nine pre-existing findings in pinned upstream
`.specify` scripts; those vendored files were not changed or claimed lint-clean.

The suite covers URL/SSRF policy; DNS mixed-address rejection; redirects and
robots; real loopback HTTP gzip, decompression limits, content types and timeout;
metadata/topic contracts; authenticated API requests; a real uvicorn TCP smoke
test; duplicate input/idempotency; concurrent claims; cancellation and stale
fencing; content integrity; and a real Iceberg crash-after-commit replay.
The real server fixture shuts down before the test exits.

Known upstream warnings: Starlette's installed test client deprecates httpx in
favor of httpx2, and Iceberg warns that the first predicate overwrite matches no
old rows. Neither warning is suppressed or claimed to be an application failure.
Remote PostgreSQL/MySQL/GCS/catalog/Trino/BigQuery and actual Argo execution remain
unverified. The cloud test deliberately skips rather than returning mock success.
