"""Shared path argument parsing and validation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence


def normalize_paths(paths: Iterable[Path | str] | None) -> list[Path]:
    """Normalize a list of paths to absolute, resolved Paths."""
    return [Path(p).expanduser().resolve() for p in (paths or [])]


def build_path_patterns(paths: Sequence[Path]) -> list[str]:
    """Build file:* patterns for capability contracts."""
    return [f"file:{p}/**" for p in paths]


def is_path_allowed(candidate: Path, allowed_paths: Sequence[Path]) -> bool:
    """Return True if candidate is within any allowed path."""
    return any(candidate == allowed or allowed in candidate.parents for allowed in allowed_paths)


def is_pathlike_arg(token: str) -> bool:
    """Heuristic for path-like arguments."""
    if token in {".", "..", "~"}:
        return True
    if token.startswith(("/", "./", "../", "~")):
        return True
    return "/" in token


def _find_path_start(token: str) -> int | None:
    """Find the first index that looks like a path start in a flag token."""
    for i in range(len(token)):
        if token[i] in {"/", "~"}:
            return i
        if token[i : i + 2] == "./":
            return i
        if token[i : i + 3] == "../":
            return i
    return None


def extract_path_args(args: Sequence[str]) -> list[str]:
    """Extract path-like arguments using a consistent heuristic."""
    paths: list[str] = []

    for arg in args:
        if not arg:
            continue

        if "=" in arg:
            _, value = arg.split("=", 1)
            if is_pathlike_arg(value):
                paths.append(value)
                continue

        if arg.startswith("--"):
            # Treat long flags as non-path unless they use --flag=/path form.
            continue

        if arg.startswith("-"):
            idx = _find_path_start(arg)
            if idx is not None:
                paths.append(arg[idx:])
            continue

        if is_pathlike_arg(arg):
            paths.append(arg)

    return paths


def resolve_path_arg(value: str, cwd: Path) -> Path:
    """Resolve a path argument relative to cwd (if not absolute)."""
    expanded = Path(value).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (cwd / expanded).resolve()
