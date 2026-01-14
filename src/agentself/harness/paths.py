"""Default filesystem locations for harness state."""

from __future__ import annotations

import os
from pathlib import Path


def agentself_home() -> Path:
    env_home = os.environ.get("AGENTSELF_HOME")
    if env_home:
        return Path(env_home).expanduser()
    return Path.cwd() / ".agentself"


def attach_socket_default() -> Path:
    return agentself_home() / "repl.sock"


def attach_history_default() -> Path:
    return agentself_home() / "attach_history"


def state_dir_default() -> Path:
    return agentself_home() / "state"


def safe_root_default() -> Path:
    return agentself_home() / "sandboxes" / "safe"
