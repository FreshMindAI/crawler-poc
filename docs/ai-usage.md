# AI, services, dependencies and provenance

AI coding assistants and CLI tooling assisted with assignment interpretation,
official-source research, Spec Kit specifications/decisions, architecture design,
Python implementation, synthetic fixtures/labels, automated tests, debugging,
cloud deployment diagnostics, and documentation.

**AI tools and models used:**
- **Claude Code & Claude Opus** — architecture synthesis, Spec Kit specification and design review, and implementation refinement.
- **GitHub Copilot CLI & GitHub CLI (`gh`)** — interactive terminal development, test/lint execution, repository management, and Cloud Run deployment diagnostics.
- **GPT-6.1 Sol (`gpt-6.1-sol`)** — core Python pipeline implementation, Spec Kit artifact generation, security/SSRF review, and regression test authoring.
- **Gemini 4 Argon (`gemini-4-argon`)** — Cloud Run container & worker orchestration, headless Chromium fallback optimization, live deployment verification, and release documentation.

Outputs were validated with automated tests (`111 passed, 1 skipped`), static analysis (`ruff`, `mypy`), and live endpoints; synthetic labels are not a substitute for an independent human-annotated relevance study.

Tools actually used include Python/pypdf for the supplied PDF, PowerShell, Git,
the existing Specify CLI/help, pinned public Spec Kit source, pytest, Ruff, mypy
and the project's HTTP/data libraries. Later work used Computer Use for bounded
private-browser observation and Playwright for isolated headless fixture tests;
neither is a third-party crawl/extraction service. A modern Specify package bootstrap failed
TLS; the global tool was not upgraded. No claim is made that every Spec Kit slash
command ran. No subagents, hosted NLP models, Rust build, cloud deployment,
container build or remote Kubernetes/BigQuery/Trino execution was used.

The optional POC web workspace was also AI-assisted, using the confirmed product/
design context and Impeccable guidance. It adds plain HTML/CSS/JavaScript served
by FastAPI, not an external frontend service. Node was used only to check JS
syntax. Playwright UI tests use synthetic content and an isolated local API/
worker; they are not public-site crawls or an independent accessibility audit.

Runtime services are target websites and, **only after explicit configuration
and authorization**, operator MySQL, remote PostgreSQL, object storage/catalog,
Trino and BigQuery. Argo is orchestration infrastructure. None provides outsourced
crawling/extraction/classification. No CAPTCHA solver, scraping proxy, managed
crawler, extraction API or external LLM inference API is used.

Principal libraries: aiohttp (HTTP), Protego (robots), lxml/Trafilatura
(HTML/text), YAKE (local keyphrases), FastAPI/Pydantic (API/contracts), SQLAlchemy
(durable control state), PyArrow/PyIceberg (real Iceberg/Parquet), and official
Google/Trino/MySQL/PostgreSQL clients for data infrastructure. Exact tested
versions are in `requirements-lock.txt`. The lock pins versions, **not artifact
hashes**, and includes test/data dependencies; platform wheel resolution and a
clean image build still need validation.

Optional renderer versions are pinned separately in
`requirements-browser-lock.txt`: Playwright 1.64.1, pyee 14.0.0 and greenlet
3.5.6. They were installed only in the project environment. Local tests use the
existing Edge executable, no browser binary download or profile import. The
separate browser Dockerfile would provision Chromium during a future approved
image build; that build and Linux/sandbox dependency review have not run.

Pinned Spec Kit source revision:
`2ee2b1e8005905db05f5717300a469b3068b908f`; upstream MIT notice is retained in
`.specify\UPSTREAM-LICENSE.txt`. Its templates/scripts retain upstream provenance;
thin Copilot wrappers are project-specific.

HTML fixtures were authored synthetically for this project; they are not copies
of publisher pages. The supplied assignment PDF is summarized and not
redistributed. Original public URL strings are retained for reproducibility.
Live raw/content files stay under ignored `var` and must not enter the submission.

`docs\evidence\dependencies.json` is generated from installed distribution
metadata, not a legal license opinion or complete vulnerability/SBOM attestation.
Review transitive notices and provider/model terms before redistribution. No
pretrained model was downloaded; its exact license/revision remains a gate.
