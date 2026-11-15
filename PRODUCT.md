# Product

## Register

product

## Users

Evaluators and developers testing a single URL or a bounded URL list during a POC demonstration.
They need to see what the crawler actually returned, including failed attempts.

## Product Purpose

Provide a same-origin interface to submit a crawl, monitor its durable job,
and inspect metadata, readable body, page type, ranked topics and errors.
The existing Python API and separate worker remain the execution model.

## Brand Personality

Clean, neutral, factual. Use POC branding only, without BrightEdge branding.

## Anti-references

No marketing landing page, decorative effects, fabricated success metrics,
or dashboards filled with unrelated controls.

## Design Principles

- Explicit single-URL and multiple-URL modes with one primary submission action.
- Keep each URL's outcome and body separate; failures must not hide sibling results.
- Show observed states, never invented progress percentages.
- Keep extracted content separate from trusted interface copy.
- Preserve access to plain text and structured JSON.
- Keep setup and failures understandable during a live demonstration.

## Accessibility & Inclusion

Responsive and keyboard-friendly, with readable contrast, visible focus,
semantic forms and polite status announcements. Do not rely on color alone.
