---
description: Get oriented with the repository structure and concepts
---

# Repository Primer

This is **agentself**, a capability-based REPL harness for coding agents. The core idea: provide agents with a persistent Python REPL they can use to execute code, introspect themselves, and modify their own behavior—all within controlled capability boundaries.

## Conceptual Architecture

### The Harness
The central runtime is a "harness"—a persistent Python subprocess that agents connect to via MCP (Model Context Protocol). Search for terms like `harness`, `repl`, `subprocess`, or `attach` to understand how agents connect and execute code.

### Capabilities
All resource access goes through capability objects that declare contracts (what they can read, write, execute, or access over network). Look for `capability`, `contract`, `guard`, or `permission` to understand the security model.

Key capability types:
- **Filesystem**: Controlled file access with path restrictions
- **Command line**: Allowlisted shell command execution
- **Skills**: Read-only access to the skill registry

### Skills Registry
Skills are discoverable units of functionality with metadata. Search for `skill`, `registry`, `discovery`, or look for `SKILL.md` files to understand how skills are defined and loaded.

### MCP Integration
The harness exposes itself as an MCP server. Search for `mcp`, `server`, or `fastmcp` to understand the protocol integration.

## Where to Look

| To understand... | Search for... | Or look in... |
|------------------|---------------|---------------|
| Overall design | `architecture`, `spec` | Documentation directory |
| How agents connect | `attach`, `harness`, `bootstrap` | Source root |
| Security model | `capability`, `contract`, `guard` | Source root |
| Available skills | `SKILL.md`, `registry` | Skills directory |
| Design decisions | `ADR`, `decision` | Documentation directory |
| Test patterns | `test_`, `pytest` | Tests directory |

## Key Files (well-known)

- `pyproject.toml` — Project metadata, dependencies, and tool configuration
- `AGENTS.md` — Shared rules for all AI agents working on this repo
- `README.md` — Project overview and quick start
