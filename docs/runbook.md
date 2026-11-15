# Operations, safety and recovery

## Configuration

`CRAWLER_` environment variables are validated by `Settings`. Defaults: four
workers (maximum 32 per process), 20-second whole-fetch budget, five page redirect
hops, three attempts, 5 MiB wire / 10 MiB decoded page caps, 512 KiB robots cap,
one-second configured origin delay, 120-second job lease, 60 authenticated API
requests/minute and 10,000 combined nonterminal/unpublished admission slots.
API bodies are capped at 64 KiB with a ten-second body-read timeout.

`CRAWLER_MAX_WIRE_BYTES` controls downloaded bytes; `CRAWLER_MAX_BYTES` controls
decoded bytes. Each setting has a 20 MiB maximum. Effective wire allowance is
the smaller of the configured wire cap and the current page/robots decoded cap,
so reducing `MAX_BYTES` still tightens both bounds. Existing explicit settings
take precedence; `.env.example` is not auto-loaded. The decoded default changed
after a measured 5,750,759-byte HTML page exceeded the original 5 MiB cap; the
download limit and decompression-bomb protection remain enforced.

Raw/clean bodies are at most the fetch cap / 250,000 extracted characters.
Topics default to five, maximum ten. Returned body slices are at most 64,000
characters. Topic-language support uses HTML language evidence; missing evidence
currently assumes English. Native parser memory amplification still requires
deployment limits and realistic tests.

Robots: standards-aware Protego rules; configured product token; missing/other
4xx permit except 401/403 deny; 429/5xx/network errors conservatively fail with
bounded retries. Successful policy caches expire after one hour. All robots
redirects are guarded, with five followed redirects. RFC 9309 does not standardize
`Crawl-delay`; this POC uses configured origin delay, not that extension. Operators
must configure any stricter site policy. Never evade denial or raise bounds merely
to force the assignment sample links to pass.

The 401/403 robots denial is a deliberately stricter operator policy, not an
RFC requirement or proof that the article itself rejects access. RFC 9309
section 2.3.1.3 permits access when robots is unavailable with 4xx; the current
profile does not exercise that option. Parsed disallow rules, actual target
401/403 and unreachable robots remain distinct conditions. Do not describe a
robots-only observation as a measured article response.

Extraction/classifier v3 retains the v2 dialog/navigation/hidden pruning and scopes headings
to semantic main/article content, and separates metadata/paragraph sentences
before YAKE. Microdata and combined identifier/price fact labels supplement
JSON-LD product evidence. A bounded visible-text fallback preserves repeated
records when precision-focused extraction retains less than one quarter of
visible content (at least five repeated blocks and over 400 visible characters).
`metadata.body_extraction`, `content_scope` and optional `product_evidence`
record the strategy; fallback also emits `structured_content_fallback`.
This is a heuristic, not a guarantee of extraction precision. Existing stored
v1 results are not silently rewritten; use a new generation to reprocess.

V3 adds bounded JSON-LD/keywords/author/time/breadcrumb/image/link evidence,
homepage classification, and weighted topics with raw/adjusted lower-is-better
scores. Repeated contained phrases and evidenced article publisher suffixes are
excluded; semantic quality is not certified. New detail fields and complete topic
scores persist in `metadata.extracted_details_json`; pipeline/attempt timings
persist in `metadata.timings_ms`. These are per-result observations, not a
replacement for timing histograms, full attempt history or remote telemetry.

Optional rendering uses `CRAWLER_BROWSER_FALLBACK=true` and an already provisioned
`msedge`, `chrome` or `chromium` channel. It is disabled by default and never
retries HTTP denial/error or detected challenges. Only successfully fetched
text-empty script shells qualify. All resource traffic is fulfilled through
SafeFetcher; a reject-only temporary local endpoint/failing DNS blocks native
browser egress. Never replace this with `route.continue_`, preflight-only DNS or
ignored certificate errors. Resource redirects/new page navigation, frames,
workers, non-GET requests and unsupported protocols are not unrestricted.
Default 16-request limit, decoded-resource and DOM caps, process slot and timeout
details are in `architecture-alignment.md`. Browser time is an additional bounded
phase; browser CPU/RSS hard supervision and Linux sandbox compatibility remain
deployment requirements, not local-test guarantees.

DNS answer validation happens inside the connector resolver; private/mixed
answers are rejected. Redirects are manual, ambient proxies/cookies are disabled,
and TLS verification remains enabled. Production must add network-level egress
controls. Local test transports are isolated test wiring, not a runtime bypass.
Azure's platform virtual address `168.63.129.16` is additionally denied despite
general IP classification; platform context:
https://learn.microsoft.com/en-us/azure/virtual-network/what-is-ip-address-168-63-129-16

## Normal operation

Start API/worker with the same database and object root. Public reads/writes need
the API key; liveness/readiness are minimal unauthenticated endpoints. Metrics
require authentication. No raw retrieved HTML is served or logged.

Failed jobs retain observed HTTP status and content type. A known page response
retains its final URL; a robots-only failure leaves page `final_url` null.
`metadata.failure_stage` and query/fragment-redacted `metadata.failure_url`
identify the failing operation; byte-limit failures also include string-valued
`failure_limit_bytes` and `failure_observed_bytes`. These fields survive outbox
publication in Iceberg's existing `metadata_json`; no schema migration is needed.
They are terminal-attempt evidence, not a complete historical attempt log.
Robots 401/403 uses reason `robots_access_denied`; actual parsed disallow rules
still use `robots_disallowed`. Both keep the existing robots-disallowed outcome.

Non-200 response bodies are not decoded: HTTP failure status must not be hidden
by an oversized or malformed error page. Transient status retries accept both
delta-seconds and HTTP-date `Retry-After`, with a 60-second delay cap; malformed
or past values add no delay. Attempt counts and origin pacing are unchanged.

Reusing URL/generation/top-k within a principal deduplicates logical jobs. A
conflicting idempotency key returns 409. API and batch principals are separate.
This is a single-operator POC, not multi-tenant identity/authorization. API keys
must be rotated through approved configuration/restarts; dual-key rotation is not
implemented. Disable/rate-limit public OpenAPI/docs at ingress if required.

Pending+unpublished capacity produces 429/API or an operator command failure.
Run workers and publisher, then resume the same immutable input/run ID. Do not
load an unbounded source into the sequential shard DAG. SQL request counters
coordinate the authenticated request budget across API processes.

## Failure/replay

| Failure | Safe response |
|---|---|
| Worker/pod dies | Preserve DB; reclaim expired lease with a higher fence; bounded attempts prevent infinite retry |
| Caller cancels | Job becomes terminal and invalidates the worker token; canceled work is not analytically published |
| Object write precedes failed DB commit | Object may be unreferenced; retain for scoped approved reconciliation/GC |
| SQL terminal commit succeeds | Job/result/latest-success/outbox are atomic |
| Iceberg commit succeeds before ack | Restart single publisher; compare deterministic batch event IDs, then acknowledge without append duplication |
| Publication mismatch/partial batch | Stop publication and investigate; do not acknowledge/delete or blindly append |
| Source content/columns/month changes | Use a new source/run identity; mutable sources need an explicit snapshot design |
| Catalog/identity expires | Stop new publication; preserve outbox; restore approved identity, then retry and reconcile |
| Upstream denial/size/robots failure | Keep typed failure; no proxy/CAPTCHA/paywall bypass |

`crawler reconcile` checks that the configured whole queue and outbox have drained.
It is **operational drain reconciliation**, not proof of object completeness or
cross-engine equality. The workflow report step and opt-in cloud tests compare
real ledger/Trino/BigQuery batch counts; full normalized-value checks and remote
fault drills remain release gates.

Unexpected worker exceptions log only a fixed safe message and recover by lease
expiry. CLI exceptions print their type, not driver messages that could contain a
DSN or sensitive URL. For diagnosis, use safe job IDs, counts, reason codes and
approved platform diagnostics; never paste credentials/full pages into logs.

## Retention/deletion and shutdown

No destructive retention job is enabled. The POC retains SQL lineage/outbox,
content and Iceberg history until the owner sets legal/freshness/cost policy.
Before production, define raw/clean/metadata/backup retention and deletion across
objects, latest projection, table delete/snapshot expiration and backups. Removing
one latest row does not erase historical content. Do not publish crawled objects
or the `var` directory with the source submission.

On incident, pause admission/worker claims, retain DB/outbox/metadata evidence,
let bounded active requests finish or expire leases, and reconcile before restart.
Roll back the application to a compatible immutable image; never reset/delete
committed analytical history to make counts look correct. Delete only named,
approved test resources during teardown; do not delete a namespace/bucket broadly
if it is shared.
