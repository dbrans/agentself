"""ChangeTracker: Track runtime modifications to the agent.

This module provides the mechanism for tracking what changes the agent
makes at runtime (tool modifications, system prompt changes, etc.)
so they can later be persisted to source files.
"""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from agentself.agent import Agent


@dataclass
class ToolChange:
    """Record of a tool modification."""

    name: str
    original_source: Optional[str]
    current_source: str
    current_impl: Callable
    timestamp: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "original_source": self.original_source,
            "current_source": self.current_source,
            "timestamp": self.timestamp,
        }


@dataclass
class PromptChange:
    """Record of a system prompt modification."""

    original: str
    current: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentChanges:
    """Collection of all changes made to an agent."""

    tools: dict[str, ToolChange] = field(default_factory=dict)
    prompt: Optional[PromptChange] = None

    def has_modifications(self) -> bool:
        """Check if there are any uncommitted modifications."""
        return bool(self.tools) or self.prompt is not None

    def summary(self) -> str:
        """Get a human-readable summary of changes."""
        lines = []
        if self.tools:
            lines.append(f"Modified tools: {', '.join(self.tools.keys())}")
        if self.prompt:
            lines.append("System prompt modified")
        return "\n".join(lines) if lines else "No changes"


class ChangeTracker:
    """Tracks runtime modifications to an agent.

    The tracker maintains a baseline snapshot of the agent's state
    and records all modifications made since that baseline.
    """

    def __init__(self, agent: Agent):
        self.agent = agent
        self._baseline_prompt = agent.system_prompt
        self._baseline_tools: dict[str, str] = {}
        self._changes = AgentChanges()

        # Snapshot baseline tool sources
        self._snapshot_tools()

    def _snapshot_tools(self):
        """Take a snapshot of current tool sources."""
        for name, spec in self.agent._tool_specs.items():
            try:
                source = inspect.getsource(spec.implementation)
                self._baseline_tools[name] = source
            except (OSError, TypeError):
                self._baseline_tools[name] = ""

    def record_tool_change(self, name: str, new_impl: Callable, new_source: str):
        """Record a tool modification."""
        original = self._baseline_tools.get(name)
        self._changes.tools[name] = ToolChange(
            name=name,
            original_source=original,
            current_source=new_source,
            current_impl=new_impl,
        )

    def record_prompt_change(self, new_prompt: str):
        """Record a system prompt modification."""
        self._changes.prompt = PromptChange(
            original=self._baseline_prompt,
            current=new_prompt,
        )

    def get_changes(self) -> AgentChanges:
        """Get all recorded changes."""
        return self._changes

    def reset_baseline(self):
        """Reset the baseline after a commit."""
        self._baseline_prompt = self.agent.system_prompt
        self._snapshot_tools()
        self._changes = AgentChanges()

    def get_modified_tool_names(self) -> list[str]:
        """Get names of all modified tools."""
        return list(self._changes.tools.keys())

    def is_tool_modified(self, name: str) -> bool:
        """Check if a specific tool has been modified."""
        return name in self._changes.tools
