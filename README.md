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
./scripts/run-safe-harness.sh

# Attach and poke around (user attach use-case)
./scripts/attach-repl.sh

# Start in background with logs + pid file
./scripts/harness-start.sh

# Tail harness logs
./scripts/harness-logs.sh

# Stop the background harness
./scripts/harness-stop.sh
```

Notes:
- The safe profile installs read-only `fs` and an allowlisted `cmd` capability (default: `ls`, `cat`, `pwd`).
- Override the allowlist by passing `--allow-cmd` flags to `run-safe-harness.sh`.
- The attach client refuses when the REPL is busy (use `--wait` to block).
- Enable logging with `AGENTSELF_LOG_LEVEL=DEBUG` (or pass `--log-level debug`).
- Debug logs include REPL execs and capability calls (fs/cmd + MCP relay).
- Attach supports line editing + history; Shift-Enter for new lines when `prompt_toolkit` is installed.
- Background logs are timestamped under `_tmp/agentself-*.log`.

## Skills

Skills live under `skills/` with a `SKILL.md` per skill (YAML frontmatter for metadata).
Set `AGENTSELF_SKILLS_DIRS` (path-separated) to add more roots.

In the REPL (safe profile), use:
- `skills.list()` for metadata
- `skills.path("<name>")` for the skill directory
- `skills.files("<name>")` to list files
- `skills.show("<name>")` to show `SKILL.md`
- `skills.fs` / `skills.cmd` for read-only access to `skills/`

Tip: use `rg`/`grep` on `skills/` for quick searching.

## MCP config

The harness can auto-install MCP servers from `mcp.json` (Claude Code format).
Disable auto-install with `--no-mcp-config`.
Environment variables in `mcp.json` are expanded (e.g., `${CONTEXT7_API_KEY}`).
- Optional: `--log-file ./_tmp/agentself.log` to write logs to a file.

## Philosophy

- Stay simple and nimble
- Prioritize homoiconicity of code, data, prompts, workflows, and knowledge
- The agent can read and write itself

## Docs

See `docs/INDEX.md` for the documentation entry point.
