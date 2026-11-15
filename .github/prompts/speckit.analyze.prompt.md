---
description: Analyze the crawler specification against the pinned Spec Kit command.
---

Read `.specify/templates/commands/analyze.md` and execute its read-only analysis procedure.
Use `.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireSpec -RequireTasks -IncludeTasks`
for its `{SCRIPT}` placeholder. Resolve the active feature through `.specify/feature.json`.
Report findings honestly; a prerequisite check alone is not semantic analysis.
Do not invoke extension hooks without the host's normal permission checks.

