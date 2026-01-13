"""AgentSelf: A capability-based agent framework.

This package provides:
- Capability protocol for controlled access to external resources
- FileSystemCapability: Scoped file read/write
- CommandLineCapability: Shell command execution with allowlists

The Bootstrap REPL (in agentself.harness) provides:
- FastMCP server for integration with coding agents (Claude Code, etc.)
- Persistent Python REPL with capability injection
- MCP hub for connecting to backend MCP servers
- State persistence across sessions

Example:
    # Start the REPL harness
    python -m agentself.harness

    # Or use capabilities directly
    from agentself import FileSystemCapability, CommandLineCapability

    fs = FileSystemCapability(allowed_paths=["./src"])
    print(fs.read("./src/main.py"))
"""

from agentself.capabilities import (
    Capability,
    CommandLineCapability,
    FileSystemCapability,
)
from agentself.core import (
    CapabilityContract,
    ExecutionResult,
)

__version__ = "0.2.0"

__all__ = [
    # Core types
    "CapabilityContract",
    "ExecutionResult",
    # Capabilities
    "Capability",
    "FileSystemCapability",
    "CommandLineCapability",
]
