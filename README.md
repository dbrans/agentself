# agentself

A self-improving coding agent.

## Status

Bootstrapping. Using Claude Code and Gemini CLI to develop the initial agent.

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check .
```

## Manual testing

```bash
# Start a safe harness + attach socket (agent integration manual testing)
uv run run-harness

# Attach and poke around (user attach use-case)
uv run attach-repl
```

Notes:
- The safe profile installs read-only `fs` and an allowlisted `cmd` capability (default: `ls`, `cat`, `pwd`).
- Override the allowlist by passing `--allow-cmd` flags to `run-harness`.
- The attach client refuses when the REPL is busy (use `--wait` to block).
- Attach to an active REPL using the same socket as the harness.
- Helper commands default to `_tmp/agentself/`; the library defaults to `.agentself/`.
- Enable logging with `AGENTSELF_LOG_LEVEL=DEBUG` (or pass `--log-level debug`).
- Debug logs include REPL execs and capability calls (fs/cmd + MCP relay).
- Attach supports line editing + history when `prompt_toolkit` is installed; use `--plain` to force readline.
- Enter submits when input is complete; Esc+Enter inserts a newline.

## Skills

Skills live under `skills/` with a `SKILL.md` per skill (or a single-file `<name>.md`).

In the REPL (safe profile), use:
- `skills.list()` for metadata
- `skills.path("<name>")` for the skill directory or file
- `skills.files("<name>")` to list files
- `skills.show("<name>")` to show the skill file
- `skills.fs` / `skills.cmd` for read-only access to `skills/`

Tip: use `rg`/`grep` on `skills/` for quick searching.

## MCP config

The harness can auto-install MCP servers from `mcp.json` (Claude Code format).
Disable auto-install with `--no-mcp-config`.
Environment variables in `mcp.json` are expanded (e.g., `${CONTEXT7_API_KEY}`).

## Philosophy

- Stay simple and nimble
- Prioritize homoiconicity of code, data, prompts, workflows, and knowledge
- The agent can read and write itself

## Docs

See `docs/INDEX.md` for the documentation entry point.
