"""Bootstrap REPL Harness.

Provides a persistent Python REPL accessible via MCP for coding agents.

Usage:
    # Start the harness as an MCP server
    python -m agentself.harness

    # Start with attach socket
    python -m agentself.harness --attach-socket ~/.agentself/repl.sock

    # Or import and use directly
    from agentself.harness import REPLSubprocess

    repl = REPLSubprocess()
    result = repl.execute("x = 1 + 1")
    print(result)
"""

from agentself.harness.repl import REPLSubprocess
from agentself.harness.server import create_server, main
from agentself.harness.attach import main as attach_main
from agentself.harness.state import StateManager, SavedState

__all__ = [
    "REPLSubprocess",
    "create_server",
    "main",
    "attach_main",
    "StateManager",
    "SavedState",
]
