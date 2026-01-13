# Repository Guidelines

## Project Structure & Module Organization
- `src/agentself/` contains the core library (src layout). Main modules live at `src/agentself/core.py` and `src/agentself/harness/`.
- `tests/` mirrors the package with `test_*.py` files (e.g., `tests/test_core.py`).
- `docs/` holds documentation notes.
- `_archive/` folders contain legacy or experimental code; avoid modifying unless explicitly needed.

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
- After completing a batch of changes, commit with a concise summary in the current branch.
- PRs should include: a concise description, how you tested (command + result), and any relevant screenshots/log snippets for CLI output changes.

## Agent-Specific Instructions
- Stay simple and nimble; prioritize homoiconicity of code, data, prompts, workflows, and knowledge.
- The agent is expected to read/write its own code; keep changes well-scoped and easy to review.
