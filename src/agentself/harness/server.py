"""FastMCP server for the REPL harness.

Exposes the REPL subprocess as MCP tools for coding agents.
Integrates with backend MCP servers via the hub.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from agentself.harness.attach_server import AttachServer
from agentself.harness.bootstrap import bootstrap_safe
from agentself.harness.logging_utils import abbreviate, configure_logging
from agentself.harness.mcp_config import install_from_config
from agentself.paths import SAFE_ROOT
from agentself.harness.repl import REPLSubprocess
from agentself.harness.runtime import HarnessRuntime, get_runtime
from agentself.harness.state import SavedState, SavedCapability

logger = logging.getLogger(__name__)


def create_server(
    name: str = "agentself-repl",
    runtime: HarnessRuntime | None = None,
) -> FastMCP:
    """Create and configure the FastMCP server.

    Args:
        name: Name for the MCP server.

    Returns:
        Configured FastMCP instance with REPL tools.
    """
    mcp = FastMCP(name)

    runtime = runtime or get_runtime()
    repl = runtime.repl
    hub = runtime.hub
    state_manager = runtime.state_manager

    @mcp.tool()
    def execute(code: str) -> dict[str, Any]:
        """Execute Python code in the persistent REPL.

        The REPL maintains state across calls - variables and functions
        defined in one call are available in subsequent calls.

        Capability method calls are automatically relayed to their
        backend MCP servers.

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

            # Use an installed capability
            execute("files = fs.list('*.py')")
        """
        logger.debug("execute code=%s", abbreviate(code))
        runtime.acquire()
        try:
            result = repl.execute(code)
            logger.debug(
                "execute result success=%s error_type=%s",
                result.success,
                result.error_type,
            )
            return asdict(result)
        finally:
            runtime.release()

    @mcp.tool()
    def state() -> dict[str, Any]:
        """Get the current state of the REPL.

        Returns:
            Dict with:
            - defined_functions: List of {name, signature, docstring}
            - variables: Dict mapping variable names to type descriptions
            - capabilities: List of registered capability names
            - history_length: Number of code blocks executed
        """
        logger.debug("state requested")
        runtime.acquire()
        try:
            result = repl.state()
            return asdict(result)
        finally:
            runtime.release()

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
            Dict with success status and capability name or error.
        """
        logger.info("register capability name=%s", name)
        runtime.acquire()
        try:
            result = repl.register_capability(name)
            if result:
                return {"success": True, "capability_name": result}
            else:
                return {"success": False, "error": f"Failed to register '{name}'"}
        finally:
            runtime.release()

    @mcp.tool()
    async def install_capability(
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        """Install an MCP server as a capability in the REPL.

        This connects to an external MCP server and makes its tools
        available as methods on a capability object in the REPL.

        Args:
            name: Name for the capability (e.g., "fs", "gmail").
            command: Command to start the MCP server.
            args: Optional argument list (skips command parsing).
            env: Optional environment variables for the server.
            cwd: Optional working directory for the server.
                    Example: "npx @anthropic/filesystem-mcp /path/to/root"

        Returns:
            Dict with:
            - success: Whether installation succeeded
            - tools: List of available tool names if successful
            - description: Capability description
            - error: Error message if failed

        Example:
            # Install a filesystem capability
            install_capability("fs", "npx @anthropic/filesystem-mcp /Users/me/project")

            # Then use it in the REPL
            execute("files = fs.list_directory('.')")
        """
        logger.info("install capability name=%s command=%s", name, command)
        runtime.acquire()
        try:
            # Connect to MCP server and get tools
            tools = await hub.install(name, command, args=args, env=env, cwd=cwd)

            # Prepare tool specs for the REPL
            tool_specs = {
                t.name: {"description": t.description, "parameters": t.parameters}
                for t in tools
            }

            # Inject relay capability into REPL
            success = repl.inject_relay_capability(name, tool_specs)

            if success:
                logger.info(
                    "installed capability name=%s tools=%s",
                    name,
                    [t.name for t in tools],
                )
                return {
                    "success": True,
                    "capability_name": name,
                    "tools": [t.name for t in tools],
                    "description": f"MCP-backed capability with tools: {', '.join(t.name for t in tools)}",
                }
            else:
                await hub.uninstall(name)
                return {"success": False, "error": "Failed to inject capability into REPL"}

        except Exception as e:
            logger.exception("install capability failed name=%s", name)
            return {"success": False, "error": str(e)}
        finally:
            runtime.release()

    @mcp.tool()
    async def uninstall_capability(name: str) -> dict[str, Any]:
        """Uninstall an MCP-backed capability.

        Disconnects from the backend MCP server. The capability object
        remains in the REPL but will error if called.

        Args:
            name: Name of the capability to uninstall.

        Returns:
            Dict with success status.
        """
        logger.info("uninstall capability name=%s", name)
        runtime.acquire()
        try:
            success = await hub.uninstall(name)
            return {"success": success}
        finally:
            runtime.release()

    @mcp.tool()
    def list_capabilities() -> list[dict[str, Any]]:
        """List all registered capabilities.

        Returns:
            List of capability info dicts, each with:
            - name: Capability name
            - type: "native" or "relay"
            - description: Capability description
        """
        logger.debug("list capabilities")
        runtime.acquire()
        try:
            return repl.list_capabilities()
        finally:
            runtime.release()

    @mcp.tool()
    def describe_capability(name: str) -> dict[str, Any]:
        """Get detailed documentation for a capability.

        Args:
            name: Name of the capability.

        Returns:
            Dict with:
            - success: Whether capability was found
            - description: Full capability documentation
            - error: Error message if not found
        """
        logger.debug("describe capability name=%s", name)
        runtime.acquire()
        try:
            result = repl.execute(f"{name}.describe()")
            if result.success:
                return {"success": True, "description": result.return_value}
            else:
                return {"success": False, "error": f"Capability '{name}' not found or has no describe()"}
        finally:
            runtime.release()

    @mcp.tool()
    def save_state(name: str = "default") -> dict[str, Any]:
        """Save current REPL state to disk.

        Persists functions, variables, capability configurations, and
        execution history. MCP-backed capabilities are saved by their
        connection commands and can be reconnected on restore.

        Args:
            name: Name for the state file. Defaults to "default".

        Returns:
            Dict with:
            - success: Whether save succeeded
            - path: Path to saved state file
            - summary: What was saved (counts)
            - error: Error message if failed
        """
        logger.info("save state name=%s", name)
        runtime.acquire()
        try:
            # Export state from REPL
            exported = repl.export_state()

            # Build saved state from exported data
            from agentself.harness.state import SavedFunction, SavedVariable

            state = SavedState(
                functions=[
                    SavedFunction(
                        name=f["name"],
                        source=f["source"],
                        signature=f["signature"],
                        docstring=f.get("docstring", ""),
                    )
                    for f in exported.get("functions", [])
                ],
                variables=[
                    SavedVariable(
                        name=v["name"],
                        var_type=v["type"],
                        value=v["value"],
                    )
                    for v in exported.get("variables", [])
                ],
                capabilities=[
                    SavedCapability(
                        name=c["name"],
                        cap_type="native",
                        source=c.get("source"),
                    )
                    for c in exported.get("native_capabilities", [])
                ] + [
                    SavedCapability(
                        name=c["name"],
                        cap_type="relay",
                        command=hub.backends[c["name"]].command if c["name"] in hub.backends else None,
                    )
                    for c in exported.get("relay_capabilities", [])
                ],
                history=exported.get("history", []),
            )

            # Save to disk
            path = state_manager.save(state, name)
            logger.info("saved state name=%s path=%s", name, path)

            return {
                "success": True,
                "path": str(path),
                "summary": {
                    "functions": len(state.functions),
                    "variables": len(state.variables),
                    "capabilities": len(state.capabilities),
                    "history_length": len(state.history),
                },
            }
        except Exception as e:
            logger.exception("save state failed name=%s", name)
            return {"success": False, "error": str(e)}
        finally:
            runtime.release()

    @mcp.tool()
    async def restore_state(name: str = "default") -> dict[str, Any]:
        """Restore REPL state from disk.

        Restores functions, variables, and reconnects to MCP servers
        for relay capabilities.

        Args:
            name: Name of the state file. Defaults to "default".

        Returns:
            Dict with:
            - success: Whether restore succeeded
            - summary: What was restored (counts and any failures)
            - error: Error message if failed
        """
        logger.info("restore state name=%s", name)
        runtime.acquire()
        try:
            # Load state from disk
            state = state_manager.load(name)
            if state is None:
                return {"success": False, "error": f"No saved state found with name '{name}'"}

            # Build state dict for REPL import
            import_data = {
                "functions": [
                    {
                        "name": f.name,
                        "source": f.source,
                        "signature": f.signature,
                        "docstring": f.docstring,
                    }
                    for f in state.functions
                ],
                "variables": [
                    {
                        "name": v.name,
                        "type": v.var_type,
                        "value": v.value,
                    }
                    for v in state.variables
                ],
                "native_capabilities": [
                    {
                        "name": c.name,
                        "source": c.source,
                    }
                    for c in state.capabilities
                    if c.cap_type == "native"
                ],
                "history": state.history,
            }

            # Import into REPL
            result = repl.import_state(import_data)

            # Reconnect relay capabilities
            relay_reconnects = []
            relay_failures = []
            for cap in state.capabilities:
                if cap.cap_type == "relay" and cap.command:
                    try:
                        tools = await hub.install(cap.name, cap.command)
                        tool_specs = {
                            t.name: {"description": t.description, "parameters": t.parameters}
                            for t in tools
                        }
                        repl.inject_relay_capability(cap.name, tool_specs)
                        relay_reconnects.append(cap.name)
                    except Exception as e:
                        relay_failures.append({"name": cap.name, "error": str(e)})

            return {
                "success": True,
                "summary": {
                    "functions_restored": result.get("functions_restored", 0),
                    "functions_failed": result.get("functions_failed", []),
                    "variables_restored": result.get("variables_restored", 0),
                    "variables_failed": result.get("variables_failed", []),
                    "capabilities_restored": result.get("capabilities_restored", 0),
                    "relay_reconnected": relay_reconnects,
                    "relay_failed": relay_failures,
                },
            }
        except Exception as e:
            logger.exception("restore state failed name=%s", name)
            return {"success": False, "error": str(e)}
        finally:
            runtime.release()

    @mcp.tool()
    def list_saved_states() -> dict[str, Any]:
        """List available saved states.

        Returns:
            Dict with list of state names.
        """
        logger.debug("list saved states")
        runtime.acquire()
        try:
            return {"states": state_manager.list_states()}
        finally:
            runtime.release()

    @mcp.tool()
    async def reset() -> dict[str, Any]:
        """Reset the REPL to a clean state.

        This terminates the current REPL subprocess, disconnects all
        MCP backends, and starts fresh.

        Returns:
            Dict with success status.
        """
        logger.info("reset repl")
        runtime.acquire()
        try:
            # Close hub connections
            await hub.close()

            # Close and restart REPL
            repl.close()
            runtime.repl = REPLSubprocess(relay_handler=runtime.relay_handler)

            logger.info("reset repl completed")
            return {"success": True, "message": "REPL reset to clean state"}
        finally:
            runtime.release()

    return mcp


# Global server instance
_server: FastMCP | None = None


def get_server(runtime: HarnessRuntime | None = None) -> FastMCP:
    """Get or create the global server instance."""
    global _server
    if _server is None:
        _server = create_server(runtime=runtime)
    return _server


def main():
    """Entry point for running the harness as an MCP server."""
    parser = argparse.ArgumentParser(description="agentself REPL harness")
    parser.add_argument(
        "--profile",
        choices=["default", "safe"],
        default="default",
        help="Bootstrap profile to apply before starting the server",
    )
    parser.add_argument("--safe-root", default=None, help="Root directory for the safe profile")
    parser.add_argument(
        "--seed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Seed the safe sandbox with example files",
    )
    parser.add_argument(
        "--allow-cmd",
        dest="allowed_commands",
        action="append",
        help="Allowlisted shell command (repeatable)",
    )
    parser.add_argument("--attach-socket", default=None, help="Unix socket path for attach server")
    parser.add_argument(
        "--mcp-config",
        default="mcp.json",
        help="Path to MCP config (Claude Code mcp.json format).",
    )
    parser.add_argument(
        "--no-mcp-config",
        action="store_true",
        help="Disable MCP config auto-install on startup.",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Log level (overrides AGENTSELF_LOG_LEVEL).",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Log file path (defaults to stderr).",
    )

    args = parser.parse_args()

    configure_logging(args.log_level, args.log_file)

    runtime = get_runtime()

    if args.profile == "safe":
        safe_root = Path(args.safe_root).expanduser() if args.safe_root else SAFE_ROOT
        logger.info(
            "bootstrap safe profile root=%s seed=%s allow_cmd=%s",
            safe_root,
            args.seed,
            args.allowed_commands,
        )
        bootstrap_safe(
            runtime,
            safe_root,
            allowed_commands=args.allowed_commands,
            seed=args.seed,
        )

    if not args.no_mcp_config and args.mcp_config:
        config_path = Path(args.mcp_config).expanduser()
        if config_path.exists():
            logger.info("loading mcp config path=%s", config_path)
            asyncio.run(install_from_config(runtime, config_path))

    if args.attach_socket:
        socket_path = Path(args.attach_socket).expanduser()
        attach_server = AttachServer(socket_path, runtime)
        thread = threading.Thread(target=attach_server.serve_forever, daemon=True)
        thread.start()
        logger.info("attach server listening socket=%s", socket_path)
        print(f"[agentself] attach server on {socket_path}", file=sys.stderr)

    server = get_server(runtime)
    server.run()


if __name__ == "__main__":
    main()
