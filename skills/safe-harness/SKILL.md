---
name: safe-harness
description: Run and inspect the safe REPL harness during prototyping.
---
# Safe harness

Use the safe harness to try REPL flows with restricted capabilities.

Quick start:
- Start the harness: `./scripts/run-harness.sh ./_tmp/agentself.attach.sock ./_tmp/safe_root`
- Attach with the REPL client.
- Use `:state`, `:caps`, `:desc <name>`, or run code.

Notes:
- The safe profile installs a read-only `fs` and an allowlisted `cmd`.
- Use `cmd.run(..., cwd=...)` to stay within the allowed root.
