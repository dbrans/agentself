"""FastMCP server for the REPL harness.

Exposes the REPL subprocess as MCP tools for coding agents.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastmcp import FastMCP

from agentself.harness.repl import REPLSubprocess, ExecutionResult, REPLState


def create_server(name: str = "agentself-repl") -> FastMCP:
    """Create and configure the FastMCP server.

    Args:
        name: Name for the MCP server.

    Returns:
        Configured FastMCP instance with REPL tools.
    """
    mcp = FastMCP(name)

    # Create the REPL subprocess (singleton for this server)
    repl = REPLSubprocess()

    @mcp.tool()
    def execute(code: str) -> dict[str, Any]:
        """Execute Python code in the persistent REPL.

        The REPL maintains state across calls - variables and functions
        defined in one call are available in subsequent calls.

        Args:
            code: Python code to execute (can be multi-line).

        Returns:
            Dict with:
            - success: Whether execution completed without errors
            - stdout: Captured standard output
            - stderr: Captured standard error
            - return_value: Result if code was an expression (JSON-serializable)
            - error_type: Type of error if failed (e.g., 'SyntaxError')
            - error_message: Error message if failed

        Examples:
            # Define a variable
            execute("x = 42")

            # Use the variable later
            execute("print(x * 2)")  # prints 84

            # Define a function
            execute("def greet(name): return f'Hello, {name}!'")

            # Call the function
            execute("greet('World')")  # returns "Hello, World!"
        """
        result = repl.execute(code)
        return asdict(result)

    @mcp.tool()
    def state() -> dict[str, Any]:
        """Get the current state of the REPL.

        Returns:
            Dict with:
            - defined_functions: List of {name, signature, docstring}
            - variables: Dict mapping variable names to type descriptions
            - capabilities: List of registered capability names
            - history_length: Number of code blocks executed

        Example:
            # After running some code
            state()
            # Returns: {
            #   "defined_functions": [{"name": "greet", "signature": "(name)", ...}],
            #   "variables": {"x": "int", "data": "list[str, ...]"},
            #   "capabilities": ["fs", "cmd"],
            #   "history_length": 5
            # }
        """
        result = repl.state()
        return asdict(result)

    @mcp.tool()
    def register_capability(name: str) -> dict[str, Any]:
        """Register an object from the REPL namespace as a capability.

        The object must have:
        - A `name` attribute (string)
        - A `describe()` method that returns documentation

        This is used for native Python capabilities defined in the REPL.

        Args:
            name: Name of the object in the REPL namespace.

        Returns:
            Dict with:
            - success: Whether registration succeeded
            - capability_name: The capability's name if successful
            - error: Error message if failed

        Example:
            # First define a capability class in the REPL
            execute('''
            class MyCapability:
                name = "my_cap"
                description = "A custom capability"

                def process(self, data):
                    return len(data)

                def describe(self):
                    return "my_cap: process(data) -> int"
            ''')

            # Then register it
            register_capability("MyCapability")
        """
        result = repl.register_capability(name)
        if result:
            return {"success": True, "capability_name": result}
        else:
            return {"success": False, "error": f"Failed to register '{name}'"}

    @mcp.tool()
    def list_capabilities() -> list[dict[str, str]]:
        """List all registered capabilities.

        Returns:
            List of capability info dicts, each with:
            - name: Capability name
            - description: Capability description
        """
        return repl.list_capabilities()

    @mcp.tool()
    def reset() -> dict[str, Any]:
        """Reset the REPL to a clean state.

        This terminates the current REPL subprocess and starts a new one.
        All variables, functions, and capabilities are lost.

        Returns:
            Dict with success status.
        """
        nonlocal repl
        repl.close()
        repl = REPLSubprocess()
        return {"success": True, "message": "REPL reset to clean state"}

    return mcp


# Global server instance
_server: FastMCP | None = None


def get_server() -> FastMCP:
    """Get or create the global server instance."""
    global _server
    if _server is None:
        _server = create_server()
    return _server


def main():
    """Entry point for running the harness as an MCP server."""
    server = get_server()
    server.run()


if __name__ == "__main__":
    main()
