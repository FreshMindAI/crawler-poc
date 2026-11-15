# POC

Proof of concept. Setup instructions, specifications, results, and supporting
details are maintained in the documentation.

## Getting started

See the [POC guide](docs/poc-guide.md) for prerequisites, local setup, API usage,
the bundled web workspace, optional browser configuration, and verification commands.

## Documentation

| Reference | Contents |
|---|---|
| [Specifications](specs/001-crawler-poc/spec.md) | Scope, requirements, decisions, and open questions |
| [Research](specs/001-crawler-poc/research.md) | Sources and technical findings |
| [Implementation plan](specs/001-crawler-poc/plan.md) | Architecture and approach |
| [Tasks](specs/001-crawler-poc/tasks.md) | Implementation tracking |
| [Evaluation](docs/poc-evaluation.md) | Measurements, evidence, and limitations |
| [Runbook](docs/runbook.md) | Configuration and operations |
| [Release plan](docs/release-plan.md) | Release gates and cadence |
| [Submission details](docs/submission-manifest.md) | Assignment coverage and remaining deliverables |
| [AI and dependency disclosure](docs/ai-usage.md) | Tooling and provenance |

## Spec Kit

Specifications are in [`specs/`](specs/). Framework templates and scripts are in
[`.specify/`](.specify/); prompts are in [`.github/prompts/`](.github/prompts/).
See the [Spec Kit analysis](docs/speckit-analysis.md) for workflow evidence and
limitations.

## Status

Local POC evidence and the public GCP Cloud Run demo (`https://crawlerbot-446234858592.europe-west1.run.app`) are live and verified. Remote multi-node Trino/Argo/BigQuery cluster execution remains documented and gated on production cluster provisioning; see the linked release and submission details.
