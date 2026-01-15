"""Repo convenience entrypoints for local workflows."""

from __future__ import annotations

import argparse
import shutil
import sys
from typing import Sequence

from agentself.paths import (
    AGENT_SKILLS_ROOT,
    REPO_ROOT,
    SKILLS_ROOT,
    TMP_ATTACH_SOCKET_PATH,
    TMP_SAFE_ROOT,
)

def _run_harness_with_args(args: list[str]) -> None:
    from agentself.harness import server as harness_server

    original_argv = sys.argv
    try:
        sys.argv = ["agentself"] + args
        harness_server.main()
    finally:
        sys.argv = original_argv


def run_harness_main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run the agentself harness with safe defaults.",
    )
    args, remainder = parser.parse_known_args(argv)
    _ = args

    for flag in ("--profile", "--safe-root", "--attach-socket"):
        if flag in remainder or any(value.startswith(f"{flag}=") for value in remainder):
            raise SystemExit(f"{flag} is not configurable in run-harness")

    TMP_SAFE_ROOT.mkdir(parents=True, exist_ok=True)

    harness_args = [
        "--profile",
        "safe",
        "--safe-root",
        str(TMP_SAFE_ROOT),
        "--attach-socket",
        str(TMP_ATTACH_SOCKET_PATH),
    ]
    harness_args.extend(remainder)

    _run_harness_with_args(harness_args)


def attach_repl_main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Attach to a running agentself REPL with safe defaults.",
        add_help=False,
    )
    args, remainder = parser.parse_known_args(argv)
    _ = args
    if "--socket" in remainder or any(value.startswith("--socket=") for value in remainder):
        raise SystemExit("--socket is not configurable in attach-repl")

    from agentself.harness.attach import main as attach_main

    original_argv = sys.argv
    try:
        sys.argv = ["agentself-attach", "--socket", str(TMP_ATTACH_SOCKET_PATH)] + remainder
        attach_main()
    finally:
        sys.argv = original_argv


def _read_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
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


def _remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def _sync_skill_sources(src: Path, dst: Path) -> None:
    for entry in sorted(src.iterdir()):
        if entry.is_dir():
            if not (entry / "SKILL.md").is_file():
                continue
            target = dst / entry.name
            if target.exists():
                continue
            shutil.copytree(entry, target)
            continue

        if entry.is_file() and entry.suffix.lower() == ".md":
            text = entry.read_text(encoding="utf-8")
            meta = _read_frontmatter(text)
            if not meta:
                continue
            name = meta.get("name") or entry.stem
            target = dst / name
            if target.exists():
                continue
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text(text, encoding="utf-8")


def _link_agent_skills(skills_dst: Path) -> None:
    for agent_dir in (".claude", ".gemini", ".codex"):
        agent_path = REPO_ROOT / agent_dir
        if not agent_path.is_dir():
            continue
        link_path = agent_path / "skills"
        _remove_path(link_path)
        link_path.symlink_to(skills_dst, target_is_directory=True)


def sync_agent_skills_main(argv: Sequence[str] | None = None) -> None:
    if argv:
        raise SystemExit("sync-agent-skills does not accept arguments")

    skills_src = SKILLS_ROOT
    skills_dst = AGENT_SKILLS_ROOT

    if not skills_src.is_dir():
        print(f"skills source not found: {skills_src}", file=sys.stderr)
        raise SystemExit(1)

    _remove_path(skills_dst)
    skills_dst.mkdir(parents=True, exist_ok=True)

    _sync_skill_sources(skills_src, skills_dst)
    _link_agent_skills(skills_dst)

    print(f"Synced skills to {skills_dst}")


__all__ = [
    "run_harness_main",
    "attach_repl_main",
    "sync_agent_skills_main",
]
