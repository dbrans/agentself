# ADR 0001: Skill Registry Roots

## Status
Accepted (2026-01-13). Updated (2026-01-14)

## Context
Skills may come from repo, plugins, or user directories. The agent should not care about source locations.

## Decision
Use a single fixed skill root:
- Default (and only) root is `./skills`.
- No environment overrides for now.

## Alternatives
- Multi-root discovery via environment variables.
- Symlink farm under `skills/_ext`.

## Consequences
- Simpler implementation and fewer configuration knobs.
- Multi-root layering can be reintroduced if/when needed.
