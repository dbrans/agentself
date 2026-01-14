# 2026-01-14 — Harness Defaults and Attach UX

## Summary
- Align attach REPL input behavior with modern Python REPLs (smart Enter).
- Centralize harness paths and default locations via `AGENTSELF_HOME`.
- Make helper scripts default to a disposable repo-local `_tmp/agentself` root.
- Updated docs/skills/runbooks to match the new defaults and attach UX.
- Added a docs update SOP and renamed `docs/session` to `docs/sessions`.
- Allow single-file skills and move docs SOP into skills for agent-triggered use.
- Added skills sync script and agent skills symlinks (.agent/skills as target).

## Decisions
- Documented in ADR: `docs/decisions/0006-harness-paths-and-attach-ux.md`.
- Documented in ADR: `docs/decisions/0007-single-file-skills.md`.

## Usage Highlights
- Start harness (defaults to `_tmp/agentself`):
  - `./scripts/run-harness.sh`
- Attach to a running harness:
  - `./scripts/attach-repl.sh`
- Prompt behavior:
  - Enter submits when input is complete.
  - Enter inserts newline when incomplete.
  - Esc+Enter always inserts newline.
- Run multiple harnesses:
  - Pass an explicit socket path or set `AGENTSELF_HOME`.

## Tests
- `uv run pytest` (most recent run: 83 tests passed)

## Open Issues (see docs/OPEN_ISSUES.md)
- MCP install allowlist.
- Attach socket cleanup policy.
