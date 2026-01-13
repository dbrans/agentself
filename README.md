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
```

Notes:
- The safe profile installs read-only `fs` and an allowlisted `cmd` capability (default: `ls`, `cat`, `pwd`).
- Override the allowlist by passing `--allow-cmd` flags to `run-safe-harness.sh`.
- The attach client refuses when the REPL is busy (use `--wait` to block).
- Enable logging with `AGENTSELF_LOG_LEVEL=DEBUG` (or pass `--log-level debug`).
- Debug logs include REPL execs and capability calls (fs/cmd + MCP relay).
- Attach supports line editing + history; Shift-Enter for new lines when `prompt_toolkit` is installed.
- Optional: `--log-file ./_tmp/agentself.log` to write logs to a file.

## Philosophy

- Stay simple and nimble
- Prioritize homoiconicity of code, data, prompts, workflows, and knowledge
- The agent can read and write itself
