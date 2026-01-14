# 2026-01-13 — Harness, Skills, MCP

## Summary
- Added safe harness profile, attach server, and attach client for REPL access.
- Implemented read-only safe capabilities (`fs`, `cmd`) with path-argument guardrails.
- Added structured logging and a single harness runner.
- Implemented skills registry and read-only `skills` capability with multi-root support.
- Added MCP config auto-install (`mcp.json`) and config loader.

## Key Decisions
- Skills are real files on disk; REPL provides read-only access (no special dev permissions).
- Skills discovery supports multiple roots via `AGENTSELF_SKILLS_DIRS` (first root wins).
- Command line capability validates path-like arguments against allowed paths.
- Logging is opt-in and scoped to `agentself` to avoid third-party debug noise.
- Single harness runner script (`run-harness.sh`); logs are handled via standard shell redirection.

## Usage Highlights
- Safe harness (foreground):
  - `./scripts/run-harness.sh`
- Attach:
  - `./scripts/attach-repl.sh`
- Logging workflow:
  - `LOG_FILE="./_tmp/harness-$(date +%Y%m%d-%H%M%S).log"`
  - `./scripts/run-harness.sh 2>&1 | tee "$LOG_FILE"`

## Tests
- `uv run pytest` (most recent run: 83 tests passed)

## Open Issues (see docs/OPEN_ISSUES.md)
- MCP install allowlist.
- Log rotation/truncation policy (if needed beyond shell redirection).
- Cleanup behavior for attach sockets.
