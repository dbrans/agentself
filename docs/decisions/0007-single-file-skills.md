# ADR 0007: Single-File Skills

## Status
Accepted (2026-01-14)

## Context
We want SOP-style skills to be easily added without creating a new directory for each one.
The skills capability already provides read-only discovery and access, so a lightweight
single-file format keeps the workflow simple while enabling agent-triggered SOPs.

## Decision
- Allow skills to be either:
  - Folder skills: `skills/<name>/SKILL.md`, or
  - Single-file skills: `skills/<name>.md`
- Single-file skills must include YAML frontmatter (at least `name` and `description`).
- Skills capability exposes `kind` and `skill_file` metadata to distinguish file vs dir.
- SOP-style docs (like "update docs") should live as skills in the `skills/` root.

## Alternatives
- Keep only folder-based skills.
- Create a separate SOP/runbook system outside of skills.

## Consequences
- Easier to add small SOPs without folder scaffolding.
- Skills discovery remains consistent via frontmatter.
- Agents can list and load skills uniformly, regardless of storage layout.
