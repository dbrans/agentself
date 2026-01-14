#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SKILLS_SRC=${1:-"$REPO_ROOT/skills"}
SKILLS_DST=${2:-"$REPO_ROOT/.agent/skills"}

if [ ! -d "$SKILLS_SRC" ]; then
  echo "skills source not found: $SKILLS_SRC" >&2
  exit 1
fi

rm -rf "$SKILLS_DST"
mkdir -p "$SKILLS_DST"

SRC="$SKILLS_SRC" DST="$SKILLS_DST" uv run python - <<'PY'
from __future__ import annotations

import os
import shutil
from pathlib import Path

src = Path(os.environ["SRC"])
dst = Path(os.environ["DST"])


def read_frontmatter(text: str) -> dict[str, str]:
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
        meta = read_frontmatter(text)
        if not meta:
            continue
        name = meta.get("name") or entry.stem
        target = dst / name
        if target.exists():
            continue
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(text, encoding="utf-8")
PY

for agent_dir in "$REPO_ROOT/.claude" "$REPO_ROOT/.gemini" "$REPO_ROOT/.codex"; do
  if [ -d "$agent_dir" ]; then
    ln -sfn "$SKILLS_DST" "$agent_dir/skills"
  fi
done

echo "Synced skills to $SKILLS_DST"
