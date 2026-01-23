# Repository Guidelines

## Project Overview
This is a capability-based REPL harness for coding agents, currently in bootstrap phase. External agents (Claude Code, Gemini CLI) are building the infrastructure toward self-hosted operation.

## Project Structure
- Source uses `src/` layout; tests mirror the package under `tests/`.
- `_archive/` folders contain legacy code; avoid modifying unless explicitly needed.

## Build, Test, and Development Commands
Use `uv` for all dependency and runtime tasks:
- `uv sync` — install/update dependencies in the local virtual environment.
- `uv run pytest` — run the test suite.
- `uv run ruff check .` — lint the codebase.
- `uv run agentself` — run the CLI entrypoint (defined in `pyproject.toml`).

## Coding Style & Naming Conventions
- Python 3.11+ only; keep code simple and direct.
- Ruff is the linter; line length is 100 (see `pyproject.toml`).
- Use `snake_case` for functions/variables, `PascalCase` for classes, and `test_*.py` for test modules.
- Prefer small, composable functions and explicit data flow; avoid “magic” behavior.

## Testing Guidelines
- Framework: `pytest` (configured via `[tool.pytest.ini_options]`).
- Place new tests under `tests/` and follow `test_<module>.py` naming.
- For new features, add at least one happy-path test and one edge case.
- Always run tests for new changes before finishing.
- Be proactive: exercise important paths beyond the obvious happy-path when testing.

## Commit & Pull Request Guidelines
- Commit messages in history are short, sentence-case summaries (e.g., “State Persistence”).
- Keep commits focused; avoid “wip” except for draft branches.

## Agent-Specific Instructions
- Stay simple and nimble; prioritize homoiconicity of code, data, prompts, workflows, and knowledge.
- The agent is expected to read/write its own code; keep changes well-scoped and easy to review.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds


<!-- BEGIN BEADS INTEGRATION -->
## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Git-friendly: Auto-syncs to JSONL for version control
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" --description="Detailed context" -t bug|feature|task -p 0-4 --json
bd create "Issue title" --description="What this issue is about" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**

```bash
bd update bd-42 --status in_progress --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task**: `bd update <id> --status in_progress`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Auto-Sync

bd automatically syncs with git:

- Exports to `.beads/issues.jsonl` after changes (5s debounce)
- Imports from JSONL when newer (e.g., after `git pull`)
- No manual export/import needed!

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

For more details, see README.md and docs/QUICKSTART.md.

<!-- END BEADS INTEGRATION -->
