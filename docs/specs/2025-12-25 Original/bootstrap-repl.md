# Bootstrap REPL Specification

Migrated from `.specs/01 Bootstrap REPL/Specification.md`.

## Goal
Provide an MCP server (REPL harness) with:
- Persistent Python REPL
- Capability objects wrapping MCP servers
- Runtime definition of functions/capabilities

## Non-goals (deferred)
- Full sandboxing
- Self-modification
- Image-based persistence
- Wasm/Pyodide isolation

## Architecture (high level)
- **REPL Harness** (FastMCP) exposes tools to an agent
- **MCP Hub** manages stdio MCP clients
- **REPL Subprocess** holds state and relay capabilities
- **State Manager** persists REPL state

## MCP tools (current design)
- `execute(code)`
- `state()`
- `install_capability(name, command, args?, env?, cwd?)`
- `uninstall_capability(name)`
- `describe_capability(name)`
- `save_state(name)` / `restore_state(name)`
- `reset()`

## Relay capabilities
- In-REPL objects that call `_relay(capability, method, kwargs)` and forward to the hub.

## Success criteria
- Execute and persist code in REPL
- Use capability objects
- Install/describe capabilities at runtime
- Persist and restore basic REPL state
