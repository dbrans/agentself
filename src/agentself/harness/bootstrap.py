"""Bootstrap helpers for predefined harness profiles."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Iterable

from agentself.harness.runtime import HarnessRuntime


DEFAULT_SAFE_COMMANDS = ["ls", "cat", "pwd"]


def seed_sandbox(root: Path) -> None:
    """Create a few files to make the sandbox immediately usable."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.txt").write_text(
        "agentself safe sandbox\n\n"
        "Try:\n"
        "  ls\n"
        "  cat README.txt\n"
    )
    (root / "notes.txt").write_text("This is a read-only sandbox.\n")


def bootstrap_safe(
    runtime: HarnessRuntime,
    root: Path,
    allowed_commands: Iterable[str] | None = None,
    seed: bool = True,
) -> None:
    """Install locked-down FS + shell capabilities into the REPL."""
    root = root.expanduser().resolve()
    if seed:
        seed_sandbox(root)

    allowed_commands = list(allowed_commands or DEFAULT_SAFE_COMMANDS)
    root_literal = repr(str(root))
    commands_literal = repr(allowed_commands)

    code = textwrap.dedent(
        f"""
        from agentself.capabilities import FileSystemCapability, CommandLineCapability

        fs = FileSystemCapability(allowed_paths=[{root_literal}], read_only=True)
        cmd = CommandLineCapability(
            allowed_commands={commands_literal},
            allowed_cwd=[{root_literal}],
            allowed_paths=[{root_literal}],
            deny_shell_operators=True,
        )
        """
    ).strip()

    runtime.acquire()
    try:
        runtime.repl.execute(code)
        runtime.repl.register_capability("fs")
        runtime.repl.register_capability("cmd")
    finally:
        runtime.release()
