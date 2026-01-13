# Bootstrap REPL Specification

## 1. Overview

### 1.1 Goal

Build an MCP server ("REPL Harness") that provides Claude Code (or any MCP-compatible agent) with:

1. A persistent Python REPL
2. Capability objects that wrap MCP servers (Gmail, filesystem, etc.)
3. The ability to define new functions and capabilities at runtime

### 1.2 Non-Goals (Deferred)

- Security sandboxing (capabilities are organizational, not security boundaries)
- Self-modification (agent cannot modify its own source yet)
- Image-based persistence (full heap snapshots)
- Wasm/Pyodide isolation

### 1.3 Success Criteria

The system is successful when:

- [ ] Agent can execute Python code in a persistent REPL via MCP
- [ ] Agent can use capability objects (e.g., `gmail.search("query")`)
- [ ] Agent can install new capabilities from MCP servers at runtime
- [ ] Agent can define functions that persist across executions
- [ ] REPL state survives harness restarts (basic serialization)

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Claude Code                          │
└─────────────────────────────────────────────────────────────┘
                              │ MCP (stdio or SSE)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    REPL Harness (FastMCP)                   │
│                                                             │
│  ┌─────────────────┐     ┌─────────────────────────────┐   │
│  │  MCP Hub        │     │   Python REPL Subprocess    │   │
│  │                 │     │                             │   │
│  │  Manages client │     │   Namespace contains:       │   │
│  │  connections to │◄───►│   - Capability stubs        │   │
│  │  backend MCP    │ IPC │   - User-defined functions  │   │
│  │  servers        │     │   - Variables               │   │
│  │                 │     │                             │   │
│  └─────────────────┘     └─────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  State Manager                                       │   │
│  │  - Serializes REPL state to disk                    │   │
│  │  - Restores on startup                              │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │ MCP (subprocess stdio)
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        gmail-mcp        slack-mcp       filesystem-mcp
        (backend)        (backend)         (backend)
```

### 2.1 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **REPL Harness** | FastMCP server exposing tools to Claude Code |
| **MCP Hub** | Manages connections to backend MCP servers |
| **REPL Subprocess** | Persistent Python interpreter with injected capabilities |
| **State Manager** | Serializes/deserializes REPL state |

---

## 3. REPL Harness (FastMCP Server)

### 3.1 MCP Tools Exposed to Agent

```python
@mcp.tool
def execute(code: str) -> ExecutionResult:
    """Execute Python code in the persistent REPL.

    Args:
        code: Python code to execute (can be multi-line)

    Returns:
        ExecutionResult with stdout, stderr, return_value, and success flag
    """

@mcp.tool
def state() -> REPLState:
    """Get the current state of the REPL.

    Returns:
        REPLState containing:
        - defined_functions: list of function names with signatures
        - variables: dict of variable names to type descriptions
        - capabilities: list of installed capability names
        - history_length: number of executed code blocks
    """

@mcp.tool
def install_capability(name: str, server_command: str) -> str:
    """Install a new capability from an MCP server.

    Args:
        name: Name to use for the capability in the REPL (e.g., "gmail")
        server_command: Command to start the MCP server (e.g., "npx @anthropic/gmail-mcp")

    Returns:
        Description of the installed capability and its available methods
    """

@mcp.tool
def uninstall_capability(name: str) -> str:
    """Remove a capability from the REPL."""

@mcp.tool
def describe_capability(name: str) -> str:
    """Get detailed documentation for a capability."""

@mcp.tool
def save_state(name: str = "default") -> str:
    """Save current REPL state to disk."""

@mcp.tool
def restore_state(name: str = "default") -> str:
    """Restore REPL state from disk."""

@mcp.tool
def reset() -> str:
    """Reset the REPL to a clean state (preserves installed capabilities)."""
```

### 3.2 Data Types

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    return_value: Any | None  # JSON-serializable representation
    error_type: str | None    # e.g., "SyntaxError", "NameError"
    error_message: str | None

@dataclass
class REPLState:
    defined_functions: list[dict]  # [{name, signature, docstring}, ...]
    variables: dict[str, str]      # {name: type_description}
    capabilities: list[str]        # ["gmail", "fs", "shell"]
    history_length: int
```

---

## 4. Capability Protocol

### 4.1 The RelayCapability Class

Capabilities are Python objects in the REPL that relay method calls to backend MCP servers.

```python
class RelayCapability:
    """A capability backed by an MCP server."""

    def __init__(self, name: str, tools: dict[str, ToolSpec]):
        self.name = name
        self._tools = tools

    def __getattr__(self, method: str):
        if method.startswith('_'):
            raise AttributeError(method)
        if method not in self._tools:
            available = ', '.join(self._tools.keys())
            raise AttributeError(
                f"'{self.name}' has no method '{method}'. "
                f"Available: {available}"
            )

        def call(**kwargs):
            # _relay is injected by the harness
            return _relay(self.name, method, kwargs)

        # Copy metadata for introspection
        tool = self._tools[method]
        call.__name__ = method
        call.__doc__ = tool.description
        return call

    def __repr__(self):
        return f"<Capability '{self.name}' with {len(self._tools)} methods>"

    def __dir__(self):
        return list(self._tools.keys()) + ['name', 'describe']

    def describe(self) -> str:
        """Return documentation for this capability."""
        lines = [f"{self.name} capability:", ""]
        for name, tool in self._tools.items():
            params = ', '.join(f"{p.name}: {p.type}" for p in tool.parameters)
            lines.append(f"  {name}({params})")
            if tool.description:
                lines.append(f"      {tool.description}")
            lines.append("")
        return '\n'.join(lines)
```

### 4.2 Relay Mechanism

The REPL subprocess cannot directly make MCP calls (async complexity). Instead:

1. Harness injects a `_relay(capability, method, kwargs)` function into REPL
2. `_relay` sends request to harness via IPC (e.g., a queue or pipe)
3. Harness makes the MCP call to the backend server
4. Result is returned through IPC to the REPL

```python
# Injected into REPL namespace
def _relay(capability: str, method: str, kwargs: dict) -> Any:
    """Relay a capability method call to the harness."""
    request = {
        "type": "relay",
        "capability": capability,
        "method": method,
        "kwargs": kwargs
    }
    # Send to harness, wait for response
    _ipc_send(request)
    response = _ipc_recv()
    if response["success"]:
        return response["result"]
    else:
        raise RuntimeError(f"{capability}.{method} failed: {response['error']}")
```

### 4.3 Installing a Capability

When `install_capability("gmail", "npx @anthropic/gmail-mcp")` is called:

1. Harness spawns the MCP server subprocess
2. Harness calls `list_tools()` on the new server
3. Harness creates a `RelayCapability` with the tool specs
4. Harness injects the capability into the REPL namespace:
   ```python
   repl.execute(f"""
   gmail = RelayCapability("gmail", {tool_specs_json})
   """)
   ```
5. Returns capability description to agent

---

## 5. REPL Subprocess

### 5.1 Subprocess Management

The REPL runs as a subprocess with bidirectional IPC:

```python
class REPLSubprocess:
    def __init__(self):
        self.process = subprocess.Popen(
            [sys.executable, "-u", "-c", REPL_BOOTSTRAP_CODE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._inject_builtins()

    def execute(self, code: str) -> ExecutionResult:
        """Execute code and return result."""

    def inject(self, name: str, value_code: str):
        """Inject a value into the REPL namespace."""

    def get_state(self) -> REPLState:
        """Get current namespace state."""
```

### 5.2 Bootstrap Code

The REPL subprocess starts with this bootstrap:

```python
REPL_BOOTSTRAP_CODE = '''
import sys
import json
import types
import traceback
from io import StringIO

# Namespace for user code
_namespace = {"__builtins__": __builtins__}

# History of executed code
_history = []

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
        result["stderr"] = traceback.format_exc()
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
        result["stdout"] = stdout_capture.getvalue()
        result["stderr"] += stderr_capture.getvalue()

    return result

def _serialize(value):
    """Serialize a value to JSON-compatible format."""
    # Handle common types, fall back to repr
    ...

# IPC loop
while True:
    line = sys.stdin.readline()
    if not line:
        break
    request = json.loads(line)

    if request["type"] == "execute":
        response = _execute(request["code"])
    elif request["type"] == "state":
        response = _get_state()
    elif request["type"] == "relay":
        # Handled specially - see relay mechanism
        ...

    print(json.dumps(response), flush=True)
'''
```

### 5.3 IPC Protocol

Simple JSON-over-stdio, one request/response per line:

**Request (harness → subprocess):**
```json
{"type": "execute", "code": "x = 1 + 1"}
{"type": "state"}
{"type": "inject", "name": "gmail", "code": "RelayCapability(...)"}
```

**Response (subprocess → harness):**
```json
{"success": true, "stdout": "", "return_value": 2, ...}
{"defined_functions": [...], "variables": {"x": "int"}, ...}
```

**Relay (bidirectional):**
```json
// subprocess → harness (outband, via stderr or separate channel)
{"type": "relay_request", "id": "abc123", "capability": "gmail", "method": "search", "kwargs": {"query": "test"}}

// harness → subprocess (response)
{"type": "relay_response", "id": "abc123", "success": true, "result": [...]}
```

---

## 6. MCP Hub

### 6.1 Backend Server Management

```python
class MCPHub:
    """Manages connections to backend MCP servers."""

    def __init__(self):
        self.backends: dict[str, MCPClient] = {}

    async def install(self, name: str, command: str) -> list[ToolSpec]:
        """Start an MCP server and return its tools."""
        client = MCPClient(command)
        await client.connect()
        tools = await client.list_tools()
        self.backends[name] = client
        return tools

    async def call(self, capability: str, method: str, kwargs: dict) -> Any:
        """Call a tool on a backend server."""
        client = self.backends[capability]
        return await client.call_tool(method, kwargs)

    async def uninstall(self, name: str):
        """Disconnect and remove a backend server."""
        if name in self.backends:
            await self.backends[name].disconnect()
            del self.backends[name]
```

### 6.2 MCP Client Implementation

Use the `mcp` Python package for client connections:

```python
from mcp import Client, StdioServerParameters

class MCPClient:
    def __init__(self, command: str):
        self.command = command
        self.client = None

    async def connect(self):
        # Parse command into program and args
        parts = shlex.split(self.command)
        params = StdioServerParameters(command=parts[0], args=parts[1:])
        self.client = await Client.connect(params)

    async def list_tools(self) -> list[ToolSpec]:
        result = await self.client.list_tools()
        return [ToolSpec.from_mcp(t) for t in result.tools]

    async def call_tool(self, name: str, kwargs: dict) -> Any:
        result = await self.client.call_tool(name, kwargs)
        return result.content
```

---

## 7. State Persistence

### 7.1 What to Persist

| Item | Persist? | Mechanism |
|------|----------|-----------|
| User-defined functions | Yes | `inspect.getsource()` + `dill` |
| Variables (JSON-serializable) | Yes | JSON |
| Variables (complex objects) | Best-effort | `dill` with fallback to repr |
| Installed capabilities | Yes | Server commands |
| Execution history | Yes | List of code strings |

### 7.2 State File Format

```json
{
  "version": 1,
  "saved_at": "2026-01-12T10:30:00Z",
  "capabilities": {
    "gmail": {"command": "npx @anthropic/gmail-mcp"},
    "fs": {"command": "npx @anthropic/filesystem-mcp", "args": {"root": "/home/user"}}
  },
  "functions": {
    "my_helper": {
      "source": "def my_helper(x):\n    return x * 2",
      "signature": "(x)"
    }
  },
  "variables": {
    "config": {"type": "json", "value": {"key": "value"}},
    "data": {"type": "dill", "value": "base64-encoded-dill-bytes"}
  },
  "history": [
    "x = 1",
    "def my_helper(x): return x * 2",
    "result = gmail.search('test')"
  ]
}
```

### 7.3 Restore Flow

1. On harness startup, check for state file
2. Reconnect to capability MCP servers
3. Re-inject capability stubs into REPL
4. Re-execute function definitions
5. Restore serializable variables
6. Log what couldn't be restored

---

## 8. File Structure

```
src/agentself/
├── __init__.py
├── harness.py              # FastMCP server, main entry point
├── repl/
│   ├── __init__.py
│   ├── subprocess.py       # REPLSubprocess class
│   ├── bootstrap.py        # REPL_BOOTSTRAP_CODE
│   └── serialization.py    # State serialization
├── hub/
│   ├── __init__.py
│   ├── client.py           # MCPClient wrapper
│   └── manager.py          # MCPHub class
├── capabilities/
│   ├── __init__.py
│   ├── relay.py            # RelayCapability class
│   └── protocol.py         # ToolSpec, CapabilitySpec
└── state/
    ├── __init__.py
    ├── persistence.py      # Save/restore logic
    └── schema.py           # State file schema
```

---

## 9. Implementation Plan

### Phase 1: Minimal REPL (No Capabilities)

**Goal**: Claude Code can execute Python and see state.

1. Create `harness.py` with FastMCP server
2. Implement `REPLSubprocess` with `execute()` and `get_state()`
3. Expose `execute` and `state` MCP tools
4. Test with Claude Code

**Deliverable**: Agent can run `execute("x = 1 + 1")` and `state()` shows `{"variables": {"x": "int"}}`

### Phase 2: Capabilities (Relay + Native)

**Goal**: Agent can use MCP-backed and native Python capabilities.

**2a: Native Capabilities (prototype first - simpler, validates protocol)**
1. Define capability protocol (name, describe())
2. Implement `register_capability()` function
3. Inject into REPL namespace
4. Test: agent defines a capability class, registers it, uses it

**2b: MCP-Backed Capabilities**
1. Implement `MCPClient` and `MCPHub`
2. Implement `RelayCapability` and injection
3. Implement relay IPC via separate pipe
4. Expose `install_capability` tool
5. Test with a simple MCP server (e.g., filesystem)

**Deliverable**:
- Agent can define `class MyCap` and `register_capability(MyCap())`
- Agent can run `install_capability("fs", "...")` then `execute("fs.list_directory('.')")`

### Phase 3: State Persistence

**Goal**: REPL state survives restarts.

1. Implement serialization for functions and variables
2. Implement `save_state` and `restore_state` tools
3. Add auto-save on harness shutdown
4. Add auto-restore on harness startup

**Deliverable**: Agent defines function, restarts harness, function still exists.

### Phase 4: Polish

1. Better error messages and stack traces
2. Capability documentation (`describe_capability`)
3. History management
4. Logging and debugging tools

---

## 10. Usage Example

Once implemented, a session might look like:

```
Agent: Let me set up the REPL with some capabilities.

> install_capability("fs", "npx @anthropic/filesystem-mcp --root /Users/me/project")
Installed 'fs' with methods: read_file, write_file, list_directory, ...

> install_capability("shell", "npx @anthropic/shell-mcp")
Installed 'shell' with methods: run, ...

> execute("""
# Read the project structure
files = fs.list_directory(".")
print(files)
""")
['src/', 'tests/', 'README.md', 'pyproject.toml']

> execute("""
# Define a helper function
def find_python_files(directory="."):
    all_files = fs.list_directory(directory, recursive=True)
    return [f for f in all_files if f.endswith('.py')]
""")
(function defined)

> execute("python_files = find_python_files()")
> state()
{
  "defined_functions": [{"name": "find_python_files", "signature": "(directory='.')"}],
  "variables": {"files": "list", "python_files": "list"},
  "capabilities": ["fs", "shell"]
}

> save_state("my_session")
State saved to my_session.json
```

---

## 11. Design Decisions

Balancing YAGNI with early prototyping of high-impact features:

| Decision | Rationale |
|----------|-----------|
| **Relay IPC via separate pipe** | Core mechanism. Mixing with stderr causes debugging pain. Small upfront cost. |
| **No async in REPL** | RelayCapability hides async. Harness handles it internally. YAGNI. |
| **Defer capability auth/config** | Start with no-auth capabilities (filesystem). Note as known limitation. |
| **Single session only** | Multi-session adds complexity without validating core value. YAGNI. |
| **Support native Python capabilities** | HIGH IMPACT: This is the path to self-development. Agent-defined capabilities are the graduation criteria. |

### 11.1 Native Capabilities (High Priority)

Beyond MCP-backed `RelayCapability`, the agent should be able to define capabilities directly in Python:

```python
# Agent writes this in the REPL:
class MyCapability:
    """A custom capability I'm building."""

    name = "my_cap"

    def process(self, data: list) -> dict:
        """Process data and return summary."""
        return {"count": len(data), "sum": sum(data)}

    def describe(self) -> str:
        return "my_cap capability:\n  process(data: list) -> dict"

# Register it
register_capability(MyCapability())
```

This is high-impact because:
1. Agent can prototype capabilities before extracting to MCP servers
2. Validates the capability protocol works for both relay and native
3. Moves toward the "agent builds its own tools" vision
4. Native capabilities can wrap MCP capabilities (composition)

The `register_capability()` function validates the object has required attributes (`name`, `describe()`) and injects it into the namespace.

---

## 12. Dependencies

```toml
[project]
dependencies = [
    "fastmcp>=0.1.0",
    "mcp>=0.1.0",
    "dill>=0.3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
]
```

---

## 13. References

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MCP Specification](https://modelcontextprotocol.io)
- Design documents:
  - `.specs/00 Bootstrap/Design.md`
  - `.specs/00 Bootstrap/2026-01-11 Agent Architecture Research and Design.md`
