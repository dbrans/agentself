# 2026-01-13 — Harness, Skills, MCP

## Summary
- Added safe harness profile, attach server, and attach client for REPL access.
- Implemented read-only safe capabilities (`fs`, `cmd`) with path-argument guardrails.
- Added structured logging and harness start/stop/log scripts.
- Implemented skills registry and read-only `skills` capability with multi-root support.
- Added MCP config auto-install (`mcp.json`) and config loader.

## Key Decisions
- Skills are real files on disk; REPL provides read-only access (no special dev permissions).
- Skills discovery supports multiple roots via `AGENTSELF_SKILLS_DIRS` (first root wins).
- Command line capability validates path-like arguments against allowed paths.
- Logging is opt-in and scoped to `agentself` to avoid third-party debug noise.

## Usage Highlights
- Safe harness (foreground):
  - `./scripts/run-safe-harness.sh ./_tmp/agentself.attach.sock ./_tmp/safe_root --log-file ./_tmp/agentself.log`
- Attach:
  - `./scripts/attach-repl.sh ./_tmp/agentself.attach.sock`
- Background harness:
  - `./scripts/harness-start.sh`
  - `./scripts/harness-logs.sh`
  - `./scripts/harness-stop.sh`

## Tests
- `uv run pytest` (multiple runs; most recent: 83 tests passed)

## Open Issues (see docs/OPEN_ISSUES.md)
- MCP install allowlist.
- Log rotation/truncation policy.
- Cleanup behavior for attach sockets.
- Default safe root for background harness in sandboxed runs.
