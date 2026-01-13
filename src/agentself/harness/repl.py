"""REPL subprocess manager.

Manages a persistent Python subprocess with JSON-over-stdio protocol.
Supports relay calls to external MCP servers during code execution.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ExecutionResult:
    """Result of executing code in the REPL."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    error_type: str | None = None
    error_message: str | None = None


@dataclass
class REPLState:
    """Current state of the REPL."""

    defined_functions: list[dict] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    history_length: int = 0


# Bootstrap code that runs in the subprocess
REPL_BOOTSTRAP = textwrap.dedent('''
    import sys
    import json
    import types
    import inspect
    import traceback
    from io import StringIO

    # Namespace for user code
    _namespace = {"__builtins__": __builtins__}

    # History of executed code blocks
    _history = []

    # Registered capabilities (native Python)
    _capabilities = {}

    # Relay capabilities (MCP-backed)
    _relay_capabilities = {}

    # Counter for relay request IDs
    _relay_id = 0

    def _serialize(value):
        """Serialize a value to JSON-compatible format."""
        if value is None:
            return None
        if isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, (list, tuple)):
            try:
                return [_serialize(v) for v in value]
            except Exception:
                return repr(value)
        if isinstance(value, dict):
            try:
                return {str(k): _serialize(v) for k, v in value.items()}
            except Exception:
                return repr(value)
        # For objects, return a useful representation
        return repr(value)

    def _get_type_str(value):
        """Get a string representation of a value's type."""
        t = type(value).__name__
        if isinstance(value, (list, tuple)) and value:
            inner = type(value[0]).__name__
            return f"{t}[{inner}, ...]" if len(value) > 1 else f"{t}[{inner}]"
        if isinstance(value, dict) and value:
            k, v = next(iter(value.items()))
            return f"dict[{type(k).__name__}, {type(v).__name__}]"
        return t

    def _relay(capability: str, method: str, kwargs: dict):
        """Relay a capability call to the harness.

        This function sends a relay request to the harness and waits for the response.
        It's used by RelayCapability objects to call MCP server tools.
        """
        global _relay_id
        _relay_id += 1
        request_id = f"relay_{_relay_id}"

        # Send relay request to harness (via stdout)
        request = {
            "type": "relay_request",
            "id": request_id,
            "capability": capability,
            "method": method,
            "kwargs": kwargs,
        }
        # Use the real stdout (not captured)
        sys.__stdout__.write(json.dumps(request) + "\\n")
        sys.__stdout__.flush()

        # Wait for response on stdin
        response_line = sys.__stdin__.readline()
        if not response_line:
            raise RuntimeError("Harness closed connection during relay")

        response = json.loads(response_line)
        if response.get("type") != "relay_response":
            raise RuntimeError(f"Unexpected response type: {response.get('type')}")
        if response.get("id") != request_id:
            raise RuntimeError(f"Response ID mismatch: expected {request_id}")

        if response.get("success"):
            return response.get("result")
        else:
            raise RuntimeError(f"Relay call failed: {response.get('error')}")

    class RelayCapability:
        """A capability backed by an MCP server.

        Method calls are relayed to the harness, which forwards them to
        the backend MCP server.
        """

        def __init__(self, name: str, tools: dict):
            self._name = name
            self._tools = tools  # {method_name: {description: str, parameters: dict}}

        @property
        def name(self):
            return self._name

        @property
        def description(self):
            return f"MCP-backed capability with {len(self._tools)} tools"

        def __getattr__(self, method: str):
            if method.startswith("_"):
                raise AttributeError(method)
            if method not in self._tools:
                available = ", ".join(self._tools.keys())
                raise AttributeError(
                    f"'{self._name}' has no method '{method}'. "
                    f"Available: {available}"
                )

            def call(**kwargs):
                return _relay(self._name, method, kwargs)

            # Copy metadata
            tool = self._tools[method]
            call.__name__ = method
            call.__doc__ = tool.get("description", "")
            return call

        def __repr__(self):
            return f"<RelayCapability '{self._name}' with {len(self._tools)} methods>"

        def __dir__(self):
            return list(self._tools.keys()) + ["name", "description", "describe"]

        def describe(self) -> str:
            """Return documentation for this capability."""
            lines = [f"{self._name} capability (MCP-backed):", ""]
            for method, tool in self._tools.items():
                desc = tool.get("description", "No description")
                lines.append(f"  .{method}()")
                lines.append(f"      {desc}")
                lines.append("")
            return "\\n".join(lines)

    # Make RelayCapability available in namespace
    _namespace["RelayCapability"] = RelayCapability
    _namespace["_relay"] = _relay

    def _execute(code: str) -> dict:
        """Execute code and return result."""
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        result = {
            "type": "execute_result",
            "success": True,
            "stdout": "",
            "stderr": "",
            "return_value": None,
            "error_type": None,
            "error_message": None,
        }

        old_stdout, old_stderr = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = stdout_capture, stderr_capture

            # Try to eval as expression first (to get return value)
            try:
                compiled = compile(code, "<repl>", "eval")
                return_value = eval(compiled, _namespace)
                result["return_value"] = _serialize(return_value)
            except SyntaxError:
                # Fall back to exec for statements
                exec(code, _namespace)

            _history.append(code)

        except Exception as e:
            result["success"] = False
            result["error_type"] = type(e).__name__
            result["error_message"] = str(e)
            # Include traceback in stderr
            stderr_capture.write(traceback.format_exc())
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
            result["stdout"] = stdout_capture.getvalue()
            result["stderr"] = stderr_capture.getvalue()

        return result

    def _get_state() -> dict:
        """Get current REPL state."""
        functions = []
        variables = {}

        for name, value in _namespace.items():
            if name.startswith("_"):
                continue
            if name == "RelayCapability":
                continue

            if callable(value) and not isinstance(value, type):
                # It's a function
                try:
                    sig = str(inspect.signature(value))
                except (ValueError, TypeError):
                    sig = "(...)"
                doc = (value.__doc__ or "").split("\\n")[0]
                functions.append({
                    "name": name,
                    "signature": sig,
                    "docstring": doc,
                })
            elif not callable(value):
                # It's a variable
                variables[name] = _get_type_str(value)

        # Combine native and relay capabilities
        all_caps = list(_capabilities.keys()) + list(_relay_capabilities.keys())

        return {
            "defined_functions": functions,
            "variables": variables,
            "capabilities": all_caps,
            "history_length": len(_history),
        }

    def _inject(name: str, code: str) -> dict:
        """Inject code into namespace."""
        try:
            exec(code, _namespace)
            _namespace[name] = _namespace.get(name)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _inject_relay_capability(name: str, tools: dict) -> dict:
        """Inject a relay capability into the namespace."""
        try:
            cap = RelayCapability(name, tools)
            _namespace[name] = cap
            _relay_capabilities[name] = cap
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _register_capability(name: str) -> dict:
        """Register a capability from the namespace."""
        if name not in _namespace:
            return {"success": False, "error": f"'{name}' not found in namespace"}
        cap = _namespace[name]
        if not hasattr(cap, "name") or not hasattr(cap, "describe"):
            return {"success": False, "error": f"'{name}' is not a valid capability (needs name and describe)"}
        _capabilities[cap.name] = cap
        return {"success": True, "capability_name": cap.name}

    def _list_capabilities() -> dict:
        """List registered capabilities."""
        caps = []
        for name, cap in _capabilities.items():
            caps.append({
                "name": name,
                "type": "native",
                "description": getattr(cap, "description", ""),
            })
        for name, cap in _relay_capabilities.items():
            caps.append({
                "name": name,
                "type": "relay",
                "description": getattr(cap, "description", ""),
            })
        return {"capabilities": caps}

    def _find_definition_in_history(name: str, is_class: bool = False) -> str:
        """Find the definition of a function or class in history."""
        keyword = "class" if is_class else "def"
        pattern = f"{keyword} {name}"

        for code in reversed(_history):
            if pattern in code:
                # Found a potential definition
                lines = code.strip().split("\\n")
                for i, line in enumerate(lines):
                    if line.strip().startswith(f"{keyword} {name}"):
                        # Extract the full definition
                        return code
        return None

    def _export_state() -> dict:
        """Export full REPL state for persistence."""
        functions = []
        variables = []

        for name, value in _namespace.items():
            if name.startswith("_"):
                continue
            if name == "RelayCapability":
                continue
            # Skip registered capabilities (handled separately)
            if name in _capabilities or name in _relay_capabilities:
                continue

            if callable(value) and not isinstance(value, type):
                # It's a function - try to get source
                source = None
                try:
                    source = inspect.getsource(value)
                except (OSError, TypeError):
                    # Can't get source via inspect, try history
                    source = _find_definition_in_history(name, is_class=False)

                if source:
                    try:
                        sig = str(inspect.signature(value))
                    except (ValueError, TypeError):
                        sig = "(...)"
                    doc = (value.__doc__ or "").split("\\n")[0]
                    functions.append({
                        "name": name,
                        "source": source,
                        "signature": sig,
                        "docstring": doc,
                    })
            elif isinstance(value, type):
                # It's a class - try to get source
                source = None
                try:
                    source = inspect.getsource(value)
                except (OSError, TypeError):
                    # Can't get source via inspect, try history
                    source = _find_definition_in_history(name, is_class=True)

                if source:
                    functions.append({
                        "name": name,
                        "source": source,
                        "signature": "",
                        "docstring": (value.__doc__ or "").split("\\n")[0],
                    })
            else:
                # It's a variable
                var_entry = {"name": name}
                # Try JSON serialization
                try:
                    json.dumps(value)
                    var_entry["type"] = "json"
                    var_entry["value"] = value
                except (TypeError, ValueError):
                    # Fall back to repr
                    var_entry["type"] = "repr"
                    var_entry["value"] = repr(value)
                variables.append(var_entry)

        # Export native capabilities (their class source)
        native_caps = []
        for name, cap in _capabilities.items():
            cap_entry = {"name": name, "type": "native"}
            try:
                cap_entry["source"] = inspect.getsource(type(cap))
            except (OSError, TypeError):
                cap_entry["source"] = None
            native_caps.append(cap_entry)

        # Export relay capabilities (their tool specs)
        relay_caps = []
        for name, cap in _relay_capabilities.items():
            relay_caps.append({
                "name": name,
                "type": "relay",
                "tools": cap._tools,
            })

        return {
            "functions": functions,
            "variables": variables,
            "native_capabilities": native_caps,
            "relay_capabilities": relay_caps,
            "history": _history.copy(),
        }

    def _import_state(state: dict) -> dict:
        """Import state from persistence."""
        results = {
            "functions_restored": 0,
            "functions_failed": [],
            "variables_restored": 0,
            "variables_failed": [],
            "capabilities_restored": 0,
            "capabilities_failed": [],
        }

        # Restore functions first (they may be used by variables)
        for func in state.get("functions", []):
            name = func["name"]
            source = func.get("source")
            if source:
                try:
                    exec(source, _namespace)
                    results["functions_restored"] += 1
                except Exception as e:
                    results["functions_failed"].append({"name": name, "error": str(e)})

        # Restore variables
        for var in state.get("variables", []):
            name = var["name"]
            var_type = var.get("type", "json")
            value = var.get("value")
            if var_type == "json":
                try:
                    _namespace[name] = value
                    results["variables_restored"] += 1
                except Exception as e:
                    results["variables_failed"].append({"name": name, "error": str(e)})
            else:
                # repr type - can't restore
                results["variables_failed"].append({"name": name, "error": "repr-only value"})

        # Restore native capabilities
        for cap in state.get("native_capabilities", []):
            name = cap["name"]
            source = cap.get("source")
            if source:
                try:
                    exec(source, _namespace)
                    # Find the class and instantiate it
                    # The source should define a class, we need to find it
                    for n, v in list(_namespace.items()):
                        if isinstance(v, type) and hasattr(v, "name") and hasattr(v, "describe"):
                            # Instantiate and register
                            instance = v()
                            _namespace[instance.name] = instance
                            _capabilities[instance.name] = instance
                            results["capabilities_restored"] += 1
                            break
                except Exception as e:
                    results["capabilities_failed"].append({"name": name, "error": str(e)})

        # Note: relay capabilities are restored by the harness reconnecting to MCP servers
        # We just record what needs to be restored
        results["relay_capabilities_to_restore"] = [
            c["name"] for c in state.get("relay_capabilities", [])
        ]

        # Restore history
        _history.clear()
        _history.extend(state.get("history", []))

        return results

    # IPC loop - read JSON from stdin, write JSON to stdout
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            request = json.loads(line.strip())
            req_type = request.get("type")

            if req_type == "execute":
                response = _execute(request["code"])
            elif req_type == "state":
                response = _get_state()
            elif req_type == "inject":
                response = _inject(request["name"], request["code"])
            elif req_type == "inject_relay_capability":
                response = _inject_relay_capability(request["name"], request["tools"])
            elif req_type == "register_capability":
                response = _register_capability(request["name"])
            elif req_type == "list_capabilities":
                response = _list_capabilities()
            elif req_type == "export_state":
                response = _export_state()
            elif req_type == "import_state":
                response = _import_state(request["state"])
            elif req_type == "ping":
                response = {"pong": True}
            else:
                response = {"error": f"Unknown request type: {req_type}"}

            print(json.dumps(response), flush=True)

        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid JSON: {e}"}), flush=True)
        except Exception as e:
            print(json.dumps({"error": f"Internal error: {e}"}), flush=True)
''')


# Type for relay handler callback
RelayHandler = Callable[[str, str, dict], Any]


class REPLSubprocess:
    """Manages a persistent Python REPL subprocess.

    Supports relay calls to external services during code execution.
    """

    def __init__(self, relay_handler: RelayHandler | None = None):
        """Start the REPL subprocess.

        Args:
            relay_handler: Callback for handling relay requests.
                          Called with (capability, method, kwargs) and should
                          return the result or raise an exception.
        """
        self.relay_handler = relay_handler
        self.process = subprocess.Popen(
            [sys.executable, "-u", "-c", REPL_BOOTSTRAP],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )
        # Verify subprocess started
        response = self._send_simple({"type": "ping"})
        if not response.get("pong"):
            raise RuntimeError("REPL subprocess failed to start")

    def _send_simple(self, request: dict) -> dict:
        """Send a request and get simple response (no relay handling)."""
        if self.process.poll() is not None:
            raise RuntimeError("REPL subprocess has terminated")

        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

        response_line = self.process.stdout.readline()
        if not response_line:
            raise RuntimeError("REPL subprocess closed stdout")

        return json.loads(response_line)

    def _send_with_relay(self, request: dict) -> dict:
        """Send a request and handle relay calls during execution."""
        if self.process.poll() is not None:
            raise RuntimeError("REPL subprocess has terminated")

        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

        # Read responses, handling relay requests
        while True:
            response_line = self.process.stdout.readline()
            if not response_line:
                raise RuntimeError("REPL subprocess closed stdout")

            response = json.loads(response_line)

            if response.get("type") == "relay_request":
                # Handle relay request
                relay_response = self._handle_relay(response)
                self.process.stdin.write(json.dumps(relay_response) + "\n")
                self.process.stdin.flush()
                continue

            # Got the actual response
            return response

    def _handle_relay(self, request: dict) -> dict:
        """Handle a relay request from the subprocess."""
        request_id = request.get("id")
        capability = request.get("capability")
        method = request.get("method")
        kwargs = request.get("kwargs", {})

        response = {
            "type": "relay_response",
            "id": request_id,
        }

        if self.relay_handler is None:
            response["success"] = False
            response["error"] = "No relay handler configured"
        else:
            try:
                result = self.relay_handler(capability, method, kwargs)
                response["success"] = True
                response["result"] = result
            except Exception as e:
                response["success"] = False
                response["error"] = str(e)

        return response

    def execute(self, code: str) -> ExecutionResult:
        """Execute Python code in the REPL.

        Args:
            code: Python code to execute (can be multi-line).

        Returns:
            ExecutionResult with success status, output, and any errors.
        """
        response = self._send_with_relay({"type": "execute", "code": code})
        return ExecutionResult(
            success=response.get("success", False),
            stdout=response.get("stdout", ""),
            stderr=response.get("stderr", ""),
            return_value=response.get("return_value"),
            error_type=response.get("error_type"),
            error_message=response.get("error_message"),
        )

    def state(self) -> REPLState:
        """Get current state of the REPL.

        Returns:
            REPLState with defined functions, variables, and capabilities.
        """
        response = self._send_simple({"type": "state"})
        return REPLState(
            defined_functions=response.get("defined_functions", []),
            variables=response.get("variables", {}),
            capabilities=response.get("capabilities", []),
            history_length=response.get("history_length", 0),
        )

    def inject(self, name: str, code: str) -> bool:
        """Inject code into the REPL namespace.

        Args:
            name: Name to bind in the namespace.
            code: Python code that defines the value.

        Returns:
            True if successful.
        """
        response = self._send_simple({"type": "inject", "name": name, "code": code})
        return response.get("success", False)

    def inject_relay_capability(self, name: str, tools: dict) -> bool:
        """Inject a relay capability into the REPL.

        Args:
            name: Name for the capability (e.g., "gmail").
            tools: Dict of tool specs {method_name: {description, parameters}}.

        Returns:
            True if successful.
        """
        response = self._send_simple({
            "type": "inject_relay_capability",
            "name": name,
            "tools": tools,
        })
        return response.get("success", False)

    def register_capability(self, name: str) -> str | None:
        """Register an object from the namespace as a capability.

        The object must have `name` and `describe()` attributes.

        Args:
            name: Name of the object in the namespace.

        Returns:
            The capability's name if successful, None otherwise.
        """
        response = self._send_simple({"type": "register_capability", "name": name})
        if response.get("success"):
            return response.get("capability_name")
        return None

    def list_capabilities(self) -> list[dict]:
        """List registered capabilities.

        Returns:
            List of capability info dicts with name, type, and description.
        """
        response = self._send_simple({"type": "list_capabilities"})
        return response.get("capabilities", [])

    def export_state(self) -> dict:
        """Export full REPL state for persistence.

        Returns:
            Dict containing functions, variables, capabilities, and history.
        """
        return self._send_simple({"type": "export_state"})

    def import_state(self, state: dict) -> dict:
        """Import state from persistence.

        Args:
            state: State dict from export_state.

        Returns:
            Dict with restore results including counts and failures.
        """
        return self._send_simple({"type": "import_state", "state": state})

    def close(self):
        """Terminate the subprocess."""
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
