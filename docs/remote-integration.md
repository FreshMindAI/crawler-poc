# Remote integration: authorization gate

No resources were discovered, deployed, billed, or accessed on the user's behalf.
The profiles are **templates**, not deployment evidence. Do not apply them until
the owner records the approved account, namespace, region, operations, quotas,
identity, budget and teardown owner in the non-secret environment inventory.

## Required choices

1. Select Azure/GCP app hosting and an authorized remote Kubernetes namespace,
   image builder/registry, remote PostgreSQL, private content store, Iceberg REST
   catalog, Trino and installed Argo controller/CRD versions.
2. Provide GCP project/location/dataset/IAM/billing authorization for BigQuery,
   even if the application runs in Azure. This implementation provides GCS
   content/input adapters; an Azure Blob adapter is not implemented. Azure app
   hosting may use approved GCS with explicit cross-cloud identity/egress costs.
3. Decide catalog/table ownership. **Never externally modify BigQuery-managed
   Iceberg files.** Prefer externally owned Iceberg with supported read access.
   If snapshot-metadata registration is selected, refresh the exact committed
   metadata URI before comparison and disclose visibility lag. A materialized
   projection requires an explicit new decision and a watermark.
4. Prove Python/REST catalog/Trino/BigQuery versions and token renewal. Managed
   Google examples are not proof for stock Kubernetes Trino.

## Configuration and least privilege

The root `Dockerfile` builds the Python API/UI application. Use `Dockerfile` as
the Cloud Build Dockerfile path and the repository root (`.`) as build context.
The image still listens on port **8000** and does not start a crawl worker.
The optional browser-worker image remains at `deploy\Dockerfile.browser`.
For the owner-approved anonymous demo, the new application image needs
`CRAWLER_AUTH_MODE=public` and `CRAWLER_BROWSER_FALLBACK=false`; it does not need
an API-key secret. Keep the Cloud Run container port at 8000. Keyed mode remains
the application default; see `poc-guide.md` for shared-data disclosure and rollback.
A remote authorized builder
must resolve the base image to a reviewed digest and publish an immutable image
digest; placeholders in Kubernetes/Argo are intentionally not deployable values.
No local Docker/Kubernetes installation was performed.

`deploy\kubernetes\application.yaml` is namespace-scoped, uses non-root processes,
read-only application roots, resource bounds, probes and a ClusterIP service.
Populate `crawler-config` through an approved secret mechanism: `database-url`,
`api-key`, `object-uri`. Use `postgresql+psycopg://...` for the control store.
Do not check populated secrets into Git. Use a dedicated schema/database;
initial tables are created by the application, not a mature migration framework.

Set provider workload identity annotations/credentials through the approved
platform integration. Automatic service-account token mounting is disabled in
the application profile; some identity systems need a dedicated projected token
volume. Configure that explicitly rather than re-enabling broad API access.

TLS ingress, platform authentication if selected, WAF/request/concurrency quotas,
network policy/egress gateway, private-service routing, workload identity,
database TLS/roles, backup/retention and external secret integration are
environment-specific **remaining deployment work**, not present guarantees.
Egress must additionally deny private/special-use/metadata targets, including
IPv6, without blocking approved private DB/catalog services. A generic allow-all
NetworkPolicy would not satisfy this.

PyIceberg uses standard named catalog configuration and its supported auth
mechanisms. `deploy\trino\crawler.properties.example` documents the REST/GCS
connector starting point, not verified credentials. `CRAWLER_TRINO_TOKEN` enables
HTTPS JWT authentication in the client; otherwise only HTTPS user identity is
sent, suitable only for an explicitly approved private/identity-protected Trino.
Google SDKs use explicitly provisioned Application Default Credentials or workload
identity; do not run discovery/login against existing corporate resources.

## Bounded Argo profile

`deploy\argo\crawl-shard.yaml` accepts one immutable source object reference and
source month. Its order is ingest -> four worker pods -> publish -> operational
reconcile -> real cross-engine reports. Each worker has its own bounded
application concurrency (default 4), so the default aggregate is at most 16,
not four total HTTP requests. Origin leases coordinate through PostgreSQL.

Use an **isolated batch control database** and a source shard of at most 1,000
unique URLs initially, below the configured pending+unpublished admission budget.
Do not submit a billion-line source to this sequential POC DAG. Production needs
an external bounded manifest scheduler and concurrent producer/consumer capacity
planning, described in the scale design. `withItems` is a fixed four-element
worker pool, never one element per URL.

The workflow mutex serializes POC workflows/publication within its installed
controller lock scope. Do not run independent publishers/maintenance outside
that ownership boundary. Cross-controller locking needs the approved Argo
database-backed synchronization configuration.

Populate `crawler-workflow-config` with the environment names in `.env.example`,
the named catalog settings, and these non-secret report identifiers:
`CRAWLER_TRINO_HOST`, `CRAWLER_TRINO_TABLE`, `CRAWLER_TRINO_USER`,
`CRAWLER_GCP_PROJECT`, `CRAWLER_GCP_LOCATION`, `CRAWLER_BIGQUERY_TABLE`.
Keep any Trino token in the secret store. Reports refuse missing configuration
or empty publications and compare each batch's expected ledger count with both
real engines. BigQuery enforces a 100 MiB billed-bytes cap per query and a client
timeout; organizational billing/IAM controls remain mandatory.

`deploy\argo\rbac.yaml` grants only namespace executor result create/patch.
The owner must validate the exact installed Argo executor/RBAC and synchronization
schema, pod termination, retry, TTL and retention settings before use.

## Compatibility evidence to retain

Record approved resource/version identifiers (never secrets), immutable image
digest, table ownership, schema/format, publication/snapshot/metadata IDs, query
job IDs/counts/bytes, normalized sample values and observed-date EXPLAIN/pruning.
Exercise a second commit, expired credentials, commit-before-ack crash, worker
termination, workflow retry and cancellation. Reconcile source aliases, terminal
outcomes, object hashes and analytical counts before declaring G2/G3 passed.

Opt-in cross-engine test:

```powershell
# Only after authorization, set all documented identifiers and credentials.
$env:CRAWLER_RUN_CLOUD_TESTS = '1'
$env:CRAWLER_TEST_BATCH_ID = '<approved-committed-batch>'
$env:CRAWLER_TEST_EXPECTED_ROWS = '<positive-ledger-count>'
.\.venv\Scripts\python.exe -m pytest -m cloud -q
```

The test queries preexisting approved data; it does not provision BigQuery tables
or make an unsupported ownership/catalog topology work automatically.
