"""Repository path constants."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

AGENTSELF_HOME = REPO_ROOT / ".agentself"
AGENTSELF_TMP_HOME = REPO_ROOT / "_tmp" / "agentself"

SKILLS_ROOT = REPO_ROOT / "skills"
AGENT_SKILLS_ROOT = REPO_ROOT / ".agent" / "skills"

ATTACH_SOCKET_PATH = AGENTSELF_HOME / "repl.sock"
ATTACH_HISTORY_PATH = AGENTSELF_HOME / "attach_history"
STATE_DIR = AGENTSELF_HOME / "state"
SAFE_ROOT = AGENTSELF_HOME / "sandboxes" / "safe"
TMP_ATTACH_SOCKET_PATH = AGENTSELF_TMP_HOME / "repl.sock"
TMP_SAFE_ROOT = AGENTSELF_TMP_HOME / "sandboxes" / "safe"


__all__ = [
    "REPO_ROOT",
    "AGENTSELF_HOME",
    "AGENTSELF_TMP_HOME",
    "SKILLS_ROOT",
    "AGENT_SKILLS_ROOT",
    "ATTACH_SOCKET_PATH",
    "ATTACH_HISTORY_PATH",
    "STATE_DIR",
    "SAFE_ROOT",
    "TMP_ATTACH_SOCKET_PATH",
    "TMP_SAFE_ROOT",
]
