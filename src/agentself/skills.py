"""Skill discovery utilities."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def _default_skills_root() -> Path:
    env_root = os.environ.get("AGENTSELF_SKILLS_DIR")
    if env_root:
        return Path(env_root).expanduser()
    return Path(__file__).resolve().parents[2] / "skills"


@dataclass
class SkillMeta:
    """Metadata for a skill."""

    name: str
    description: str
    path: Path


def _read_frontmatter(path: Path) -> dict[str, str]:
    """Parse simple YAML frontmatter (key: value pairs)."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta


class SkillRegistry:
    """Discover and load skills from disk."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root else _default_skills_root()
        self.root = self.root.expanduser().resolve()

    def list(self) -> list[SkillMeta]:
        """List available skills (metadata only)."""
        if not self.root.exists():
            return []

        skills = []
        for skill_dir in sorted(self.root.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            meta = _read_frontmatter(skill_file)
            name = meta.get("name") or skill_dir.name
            description = meta.get("description") or ""
            skills.append(SkillMeta(name=name, description=description, path=skill_file))
        return skills

    def show(self, name: str) -> str:
        """Return the full skill text."""
        path = self.path(name)
        return path.read_text(encoding="utf-8")

    def path(self, name: str) -> Path:
        """Return the SKILL.md path for a skill."""
        for meta in self.list():
            if meta.name == name:
                return meta.path
        raise FileNotFoundError(f"Skill not found: {name}")

    def list_json(self) -> str:
        """Return skill metadata as JSON."""
        payload = [
            {"name": s.name, "description": s.description, "path": str(s.path)}
            for s in self.list()
        ]
        return json.dumps(payload, indent=2)
