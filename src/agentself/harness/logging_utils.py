"""Logging helpers for the harness."""

from __future__ import annotations

import logging
import os
from pathlib import Path

DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(log_level: str | None = None, log_file: str | None = None) -> None:
    """Configure stdlib logging for the harness."""
    env_level = os.getenv("AGENTSELF_LOG_LEVEL")
    level_name = (log_level or env_level or "").upper()
    if not level_name and not log_file:
        return
    if not level_name:
        level_name = "WARNING"
    level = logging.getLevelName(level_name)
    if isinstance(level, str):
        raise ValueError(f"Invalid log level: {level_name}")

    handlers: list[logging.Handler] = []
    if log_file:
        path = Path(log_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path))
    else:
        handlers.append(logging.StreamHandler())

    for handler in handlers:
        handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))

    root = logging.getLogger()
    root.setLevel(logging.WARNING)

    logger = logging.getLogger("agentself")
    logger.setLevel(level)
    logger.propagate = False
    logger.handlers = handlers


def abbreviate(text: str, limit: int = 200) -> str:
    """Return a single-line, truncated preview string."""
    if text is None:
        return ""
    flattened = text.replace("\n", "\\n")
    if len(flattened) <= limit:
        return flattened
    return f"{flattened[:limit]}..."
