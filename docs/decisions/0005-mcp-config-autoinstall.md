# ADR 0005: MCP Config Auto-install

## Status
Accepted (2026-01-13)

## Context
We want reproducible MCP capability setup with minimal friction for manual testing.

## Decision
Support `mcp.json` (Claude Code format) and auto-install servers on harness startup. Allow disabling with `--no-mcp-config`.

## Alternatives
- Only manual install via MCP tool calls.
- Separate config format.

## Consequences
- Reproducible setup; easier manual testing.
- Requires a policy decision on ad-hoc installs (open issue).
