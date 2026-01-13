"""Tests for skills registry."""

from pathlib import Path

from agentself.skills import SkillRegistry


def _write_skill(root: Path, name: str, description: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def test_list_and_show_skills(tmp_path: Path) -> None:
    _write_skill(tmp_path, "one", "First skill")
    _write_skill(tmp_path, "two", "Second skill")

    registry = SkillRegistry(root=tmp_path)
    skills = registry.list()
    names = [s.name for s in skills]

    assert "one" in names
    assert "two" in names

    content = registry.show("one")
    assert "First skill" in content


def test_missing_skill_raises(tmp_path: Path) -> None:
    registry = SkillRegistry(root=tmp_path)
    try:
        registry.show("missing")
    except FileNotFoundError as exc:
        assert "missing" in str(exc)
