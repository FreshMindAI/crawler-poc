# POC interface

An evaluator opens the demo on a laptop in a bright meeting room and needs to
read results while discussing them. Use a light, restrained workspace.

## Visual system

Tinted stone surfaces, charcoal text and a restrained rust accent for the main
action. Use OKLCH tokens, system sans-serif for UI and system monospace for
URLs, identifiers and JSON. No downloaded fonts, icon libraries or CDN assets.

## Layout and interaction

A narrow header and a single main workspace. Form first, then an inline
job-status strip, then a readable result document. Metadata and topic columns
collapse into one column on small screens. Separate sections with whitespace
and fine rules, not nested cards. Native disclosure controls reveal JSON.
An explicit mode selector retains single-URL entry and adds a multiline batch
field. Batch results use a compact selectable URL list, with one result document
below it rather than repeating many expanded documents.

Controls use explicit labels, consistent borders and visible keyboard focus.
Loading is text-based with actual queue state, not an indeterminate percentage.
No animation is necessary for this task.
