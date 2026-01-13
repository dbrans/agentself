"""Skills capability with read-only skill filesystem access."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from agentself.capabilities.base import Capability
from agentself.capabilities.command_line import CommandLineCapability
from agentself.capabilities.file_system import FileSystemCapability
from agentself.skills import SkillRegistry

DEFAULT_SKILL_COMMANDS = ["ls", "cat", "rg", "grep", "head", "tail", "wc", "pwd"]


class SkillsCapability(Capability):
    """Expose skills metadata + a read-only view of the skills directory."""

    name = "skills"
    description = "List and inspect skills (with read-only skills.fs/skills.cmd)."

    def __init__(
        self,
        root: Path | str | None = None,
        allowed_commands: Iterable[str] | None = None,
    ) -> None:
        self.registry = SkillRegistry(root=root)
        self.root = self.registry.root
        self.fs = FileSystemCapability(allowed_paths=[self.root], read_only=True)
        self.cmd = CommandLineCapability(
            allowed_commands=list(allowed_commands or DEFAULT_SKILL_COMMANDS),
            allowed_paths=[self.root],
            allowed_cwd=[self.root],
            deny_shell_operators=True,
        )

    def list(self) -> list[dict[str, str]]:
        """List available skills (metadata only)."""
        return [
            {"name": meta.name, "description": meta.description, "path": str(meta.path.parent)}
            for meta in self.registry.list()
        ]

    def path(self, name: str) -> str:
        """Return the skill directory path."""
        return str(self.registry.path(name).parent)

    def files(self, name: str) -> list[str]:
        """List files inside a skill directory."""
        path = Path(self.registry.path(name).parent)
        if not path.exists():
            return []
        return sorted(str(p) for p in path.rglob("*") if p.is_file())

    def show(self, name: str) -> str:
        """Return the skill's SKILL.md content."""
        return self.registry.show(name)
