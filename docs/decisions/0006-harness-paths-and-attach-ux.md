# ADR 0006: Harness Paths and Attach UX

## Status
Accepted (2026-01-14)

## Context
- `~/.agentself` defaults caused permission issues in sandboxed runs.
- We want a lightweight repo-local default and a disposable default for manual testing.
- The attach client previously relied on an unsupported Shift-Enter binding.

## Decision
- Library defaults to `.agentself/` in the current working directory, overridable with `AGENTSELF_HOME`.
- Helper scripts default to `_tmp/agentself/` for disposable runs (they export `AGENTSELF_HOME`).
- Attach uses prompt_toolkit when available with smart Enter behavior:
  - Enter submits when input is complete.
  - Enter inserts a newline when input is incomplete.
  - Esc+Enter always inserts a newline.
- `--plain` remains available to force readline mode.

## Alternatives
- Keep global `~/.agentself` defaults.
- Require explicit socket/safe-root every time.
- Keep single-line input or use unsupported Shift-Enter bindings.

## Consequences
- Works in sandboxed environments and avoids cross-project state leakage by default.
- Multi-harness runs still supported via explicit socket or `AGENTSELF_HOME`.
- Attach UX matches modern REPL expectations without relying on unsupported key bindings.
