# ADR 0001: Skill Registry Roots

## Status
Accepted (2026-01-13)

## Context
Skills may come from repo, plugins, or user directories. The agent should not care about source locations.

## Decision
Implement multi-root skill discovery:
- Default root is `./skills`.
- Optional `AGENTSELF_SKILLS_DIRS` (path-separated) defines additional roots.
- First root wins on name collisions.

## Alternatives
- Single fixed root only.
- Symlink farm under `skills/_ext`.

## Consequences
- Agent can stay location-agnostic.
- Future sources can be layered without changing the agent API.
