"""REPL subprocess manager.

Manages a persistent Python subprocess with JSON-over-stdio protocol.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field, asdict
from typing import Any


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

    # Registered capabilities
    _capabilities = {}

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

    def _execute(code: str) -> dict:
        """Execute code and return result."""
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        result = {
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

        return {
            "defined_functions": functions,
            "variables": variables,
            "capabilities": list(_capabilities.keys()),
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
                "description": getattr(cap, "description", ""),
            })
        return {"capabilities": caps}

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
            elif req_type == "register_capability":
                response = _register_capability(request["name"])
            elif req_type == "list_capabilities":
                response = _list_capabilities()
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


class REPLSubprocess:
    """Manages a persistent Python REPL subprocess."""

    def __init__(self):
        """Start the REPL subprocess."""
        self.process = subprocess.Popen(
            [sys.executable, "-u", "-c", REPL_BOOTSTRAP],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )
        # Verify subprocess started
        response = self._send({"type": "ping"})
        if not response.get("pong"):
            raise RuntimeError("REPL subprocess failed to start")

    def _send(self, request: dict) -> dict:
        """Send a request to the subprocess and get response."""
        if self.process.poll() is not None:
            raise RuntimeError("REPL subprocess has terminated")

        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

        response_line = self.process.stdout.readline()
        if not response_line:
            raise RuntimeError("REPL subprocess closed stdout")

        return json.loads(response_line)

    def execute(self, code: str) -> ExecutionResult:
        """Execute Python code in the REPL.

        Args:
            code: Python code to execute (can be multi-line).

        Returns:
            ExecutionResult with success status, output, and any errors.
        """
        response = self._send({"type": "execute", "code": code})
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
        response = self._send({"type": "state"})
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
        response = self._send({"type": "inject", "name": name, "code": code})
        return response.get("success", False)

    def register_capability(self, name: str) -> str | None:
        """Register an object from the namespace as a capability.

        The object must have `name` and `describe()` attributes.

        Args:
            name: Name of the object in the namespace.

        Returns:
            The capability's name if successful, None otherwise.
        """
        response = self._send({"type": "register_capability", "name": name})
        if response.get("success"):
            return response.get("capability_name")
        return None

    def list_capabilities(self) -> list[dict]:
        """List registered capabilities.

        Returns:
            List of capability info dicts with name and description.
        """
        response = self._send({"type": "list_capabilities"})
        return response.get("capabilities", [])

    def close(self):
        """Terminate the subprocess."""
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
