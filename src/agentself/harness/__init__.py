"""Bootstrap REPL Harness.

Provides a persistent Python REPL accessible via MCP for coding agents.

Usage:
    # Start the harness as an MCP server
    python -m agentself.harness

    # Or import and use directly
    from agentself.harness import REPLSubprocess

    repl = REPLSubprocess()
    result = repl.execute("x = 1 + 1")
    print(result)
"""

from agentself.harness.repl import REPLSubprocess
from agentself.harness.server import create_server, main

__all__ = [
    "REPLSubprocess",
    "create_server",
    "main",
]
