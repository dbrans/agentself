"""agentself: A self-improving coding agent.

The agent can read and modify its own source code, track runtime changes,
and persist modifications back to files for versioning.
"""

from agentself.agent import Agent, tool
from agentself.generator import SourceGenerator
from agentself.tracker import ChangeTracker, ToolChange

__all__ = [
    "Agent",
    "tool",
    "ChangeTracker",
    "ToolChange",
    "SourceGenerator",
]

__version__ = "0.1.0"
