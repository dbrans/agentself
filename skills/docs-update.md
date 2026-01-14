---
name: docs-update-sop
description: SOP for updating docs/[decisions|specs|runbooks|usage|sessions|index|open-issues] mid-session. Trigger when a user asks to "update docs" or requests documentation consolidation or suggest it when you notice a session introduces multiple doc-worthy changes.
---

# Docs Update SOP (for "update docs" requests)

Use this workflow whenever a user asks to "update docs" mid-session.

## Step 1: Build the docs task list
Create a short checklist of what should be added/updated:
- Decisions (ADRs)
- Specs
- Runbooks
- Usage docs
- Sessions (distillation)
- Index + open issues

If there are many items, keep a running todo list in your response until done.

## Step 2: Apply updates (consolidate, don't duplicate)
Work through the checklist and update the appropriate `docs/` subfolder(s).
Prefer consolidating related info into existing docs rather than creating duplicates.

### Decisions (ADRs) — `docs/decisions/`
- Numbered `0001`, `0002`, ... in filename and header.
- Include Status (Accepted / Superseded / Obsolete / Proposed) and date.
- If a decision changes, write a new ADR and mark the old one "Superseded by 000X".
- Keep decisions short and durable.

### Specs — `docs/specs/`
- Keep for stable requirements and architecture descriptions.
- Update existing specs for refinements; create new specs for new subsystems.
- Avoid session or operational notes here.

### Runbooks — `docs/runbooks/`
- Step-by-step, actionable procedures and troubleshooting.
- Keep commands current and minimal.
- Include expected outcomes and common failure modes.

### Usage — `docs/usage/`
- Quickstart patterns, API/CLI usage, and safe defaults.
- Prefer crisp examples and short explanations.

### Sessions — `docs/sessions/`
- One file per date: `YYYY-MM-DD-<slug>.md`.
- Include summary, decisions (link to ADRs), usage highlights, tests run, and open issues.
- Keep it short and factual.

### Index + Open Issues
- Update `docs/INDEX.md` to link the latest session and any new ADRs/runbooks/specs.
- Update `docs/OPEN_ISSUES.md` if new unresolved items surfaced.

## Step 3: Write the session distillation
Create or update a dated file in `docs/sessions/` for the current day.
Include changes made during this segment and link to relevant ADRs.

## Step 4: Checkpoint (required)
End your response with a single-line sentinel so a future agent can resume from the
latest doc update. Format:

`DOCUMENT-UPDATE-CHECKPOINT: YYYY-MM-DD <short-unique-note>`

Example:
`DOCUMENT-UPDATE-CHECKPOINT: 2026-01-14 docs-updated`
