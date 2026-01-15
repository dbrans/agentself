"""Tests for skills registry."""

from pathlib import Path

from agentself.paths import SKILLS_ROOT
from agentself.skills import SkillRegistry


def _write_skill(root: Path, name: str, description: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def _write_single_skill(root: Path, name: str, description: str) -> None:
    skill_file = root / f"{name}.md"
    skill_file.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def test_list_and_show_skills(tmp_path: Path) -> None:
    _write_skill(tmp_path, "one", "First skill")
    _write_skill(tmp_path, "two", "Second skill")
    _write_single_skill(tmp_path, "single", "Single-file skill")

    registry = SkillRegistry(root=tmp_path)
    skills = registry.list()
    names = [s.name for s in skills]

    assert "one" in names
    assert "two" in names
    assert "single" in names

    content = registry.show("one")
    assert "First skill" in content

    single_content = registry.show("single")
    assert "Single-file skill" in single_content


def test_missing_skill_raises(tmp_path: Path) -> None:
    registry = SkillRegistry(root=tmp_path)
    try:
        registry.show("missing")
    except FileNotFoundError as exc:
        assert "missing" in str(exc)


def test_skill_registry_default_root() -> None:
    registry = SkillRegistry()
    assert registry.root == SKILLS_ROOT.resolve()


def test_skill_registry_default_roots() -> None:
    registry = SkillRegistry()
    assert registry.roots == [SKILLS_ROOT.resolve()]


def test_skill_registry_root_precedence(tmp_path: Path, tmp_path_factory) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path_factory.mktemp("skills_b")
    _write_skill(root_a, "dup", "First")
    _write_skill(root_b, "dup", "Second")

    registry = SkillRegistry(root=[root_a, root_b])
    skills = registry.list()

    assert skills[0].name == "dup"
    assert skills[0].description == "First"
