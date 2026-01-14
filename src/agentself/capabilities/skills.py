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
        root: Path | str | Iterable[Path | str] | None = None,
        allowed_commands: Iterable[str] | None = None,
    ) -> None:
        self.registry = SkillRegistry(root=root)
        self.roots = self.registry.roots
        self.fs = FileSystemCapability(allowed_paths=self.roots, read_only=True)
        self.cmd = CommandLineCapability(
            allowed_commands=list(allowed_commands or DEFAULT_SKILL_COMMANDS),
            allowed_paths=self.roots,
            allowed_cwd=self.roots,
            deny_shell_operators=True,
        )

    def list(self) -> list[dict[str, str]]:
        """List available skills (metadata only)."""
        payload: list[dict[str, str]] = []
        for meta in self.registry.list():
            skill_file = meta.path
            base_path = skill_file.parent if skill_file.name == "SKILL.md" else skill_file
            kind = "dir" if base_path.is_dir() else "file"
            payload.append(
                {
                    "name": meta.name,
                    "description": meta.description,
                    "path": str(base_path),
                    "skill_file": str(skill_file),
                    "kind": kind,
                }
            )
        return payload

    def path(self, name: str) -> str:
        """Return the skill base path (directory or single file)."""
        skill_file = self.registry.path(name)
        base_path = skill_file.parent if skill_file.name == "SKILL.md" else skill_file
        return str(base_path)

    def files(self, name: str) -> list[str]:
        """List files inside a skill directory."""
        base = Path(self.path(name))
        if not base.exists():
            return []
        if base.is_file():
            return [str(base)]
        return sorted(str(p) for p in base.rglob("*") if p.is_file())

    def show(self, name: str) -> str:
        """Return the skill's SKILL.md content."""
        return self.registry.show(name)
