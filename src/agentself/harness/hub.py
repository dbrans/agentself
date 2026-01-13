"""MCP Hub - manages connections to backend MCP servers.

The hub acts as an MCP client, connecting to external MCP servers
and making tool calls on behalf of the REPL.
"""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@dataclass
class ToolSpec:
    """Specification for an MCP tool."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mcp(cls, tool) -> "ToolSpec":
        """Create from MCP tool definition."""
        return cls(
            name=tool.name,
            description=tool.description or "",
            parameters=tool.inputSchema if hasattr(tool, "inputSchema") else {},
        )


@dataclass
class BackendServer:
    """A connected backend MCP server."""

    name: str
    command: str
    tools: dict[str, ToolSpec]
    session: ClientSession
    _cleanup: Any = None  # Cleanup context manager


class MCPHub:
    """Manages connections to backend MCP servers."""

    def __init__(self):
        self.backends: dict[str, BackendServer] = {}
        self._lock = asyncio.Lock()

    async def install(self, name: str, command: str) -> list[ToolSpec]:
        """Connect to an MCP server and return its tools.

        Args:
            name: Name to use for this backend (e.g., "gmail", "fs").
            command: Command to start the MCP server.

        Returns:
            List of tools provided by the server.

        Raises:
            RuntimeError: If connection fails.
        """
        async with self._lock:
            if name in self.backends:
                await self.uninstall(name)

            # Parse command
            parts = shlex.split(command)
            if not parts:
                raise ValueError(f"Invalid command: {command}")

            server_params = StdioServerParameters(
                command=parts[0],
                args=parts[1:] if len(parts) > 1 else [],
            )

            try:
                # Connect to the server
                read, write = await asyncio.wait_for(
                    stdio_client(server_params).__aenter__(),
                    timeout=30.0,
                )
                session = ClientSession(read, write)
                await session.__aenter__()
                await session.initialize()

                # Get available tools
                tools_result = await session.list_tools()
                tools = {
                    t.name: ToolSpec.from_mcp(t) for t in tools_result.tools
                }

                self.backends[name] = BackendServer(
                    name=name,
                    command=command,
                    tools=tools,
                    session=session,
                )

                return list(tools.values())

            except asyncio.TimeoutError:
                raise RuntimeError(f"Timeout connecting to MCP server: {command}")
            except Exception as e:
                raise RuntimeError(f"Failed to connect to MCP server: {e}")

    async def call(self, capability: str, method: str, kwargs: dict) -> Any:
        """Call a tool on a backend server.

        Args:
            capability: Name of the backend (e.g., "gmail").
            method: Name of the tool to call.
            kwargs: Arguments for the tool.

        Returns:
            Result from the tool call.

        Raises:
            KeyError: If capability not found.
            RuntimeError: If tool call fails.
        """
        if capability not in self.backends:
            raise KeyError(f"Capability '{capability}' not installed")

        backend = self.backends[capability]

        if method not in backend.tools:
            available = ", ".join(backend.tools.keys())
            raise KeyError(
                f"Tool '{method}' not found in '{capability}'. "
                f"Available: {available}"
            )

        try:
            result = await backend.session.call_tool(method, kwargs)
            # Extract content from result
            if hasattr(result, "content") and result.content:
                # Return first text content
                for item in result.content:
                    if hasattr(item, "text"):
                        return item.text
                return str(result.content)
            return result
        except Exception as e:
            raise RuntimeError(f"{capability}.{method} failed: {e}")

    async def uninstall(self, name: str) -> bool:
        """Disconnect from a backend server.

        Args:
            name: Name of the backend to disconnect.

        Returns:
            True if disconnected, False if not found.
        """
        async with self._lock:
            if name not in self.backends:
                return False

            backend = self.backends.pop(name)
            try:
                await backend.session.__aexit__(None, None, None)
            except Exception:
                pass  # Best effort cleanup

            return True

    def list_backends(self) -> list[dict[str, Any]]:
        """List all connected backends.

        Returns:
            List of backend info dicts.
        """
        return [
            {
                "name": b.name,
                "command": b.command,
                "tools": [
                    {"name": t.name, "description": t.description}
                    for t in b.tools.values()
                ],
            }
            for b in self.backends.values()
        ]

    def get_tools(self, capability: str) -> dict[str, ToolSpec]:
        """Get tools for a capability.

        Args:
            capability: Name of the backend.

        Returns:
            Dict of tool name to ToolSpec.
        """
        if capability not in self.backends:
            return {}
        return self.backends[capability].tools

    async def close(self):
        """Close all backend connections."""
        for name in list(self.backends.keys()):
            await self.uninstall(name)
