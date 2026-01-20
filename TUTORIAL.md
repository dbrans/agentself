# agentself Tutorial

Welcome to agentself, a capability-based REPL harness for coding agents. This tutorial focuses on advanced use cases and shows how to use the REPL both directly and through agent integration.

## What is agentself?

agentself provides a persistent Python REPL with capability-based security that can be controlled in two ways:

1. **Direct use** - Humans attach to the REPL via a socket client for interactive exploration
2. **Agent use** - Coding agents use MCP tools to execute code and manage capabilities

The same REPL instance serves both use cases simultaneously. The runtime maintains state between calls, enabling sophisticated multi-step workflows where agents build up context, define functions, and compose capabilities.

## Prerequisites

- Python 3.11 or higher
- `uv` package manager

## Installation

```bash
git clone <repository-url>
cd agentself
uv sync
```

## Architecture Overview

The harness exposes itself as an MCP server with these tools:

- `execute(code)` - Execute Python in the persistent REPL
- `state()` - Inspect REPL state (functions, variables, capabilities)
- `install_capability(name, command, ...)` - Connect an MCP server as a capability
- `uninstall_capability(name)` - Disconnect an MCP server
- `describe_capability(name)` - Get capability documentation
- `list_capabilities()` - List all registered capabilities
- `save_state(name)` / `restore_state(name)` - Persist/restore REPL state
- `list_saved_states()` - List available state snapshots
- `reset()` - Clean slate (new REPL subprocess)

Agents call these tools via MCP protocol. Humans can attach directly to the REPL for exploration and debugging.

## Quick Start

### 1. Start the Harness

Launch with the safe profile (read-only fs, allowlisted cmd):

```bash
uv run run-harness
```

The harness:
- Runs an MCP server on stdio (for agents to connect)
- Runs an attach server on `_tmp/agentself/repl.sock` (for humans to connect)
- Bootstraps the safe profile with `fs`, `cmd`, and `skills` capabilities

### 2. Direct Use - Attach to the REPL

In a new terminal:

```bash
uv run attach-repl
```

You're now in the Python REPL with capabilities pre-installed. Try:

```python
# Inspect what's available
dir()  # Shows fs, cmd, skills, state

# Check capability contracts
fs.contract()
cmd.contract()

# List available skills
skills.list()
```

**Input tips:**
- Enter submits complete statements
- Esc+Enter inserts newlines for multi-line code
- Standard readline editing works

## Understanding Capabilities

Capabilities are scoped objects that provide controlled access to resources. In safe mode:

- `fs` - Read-only filesystem scoped to `_tmp/agentself/sandboxes/safe`
- `cmd` - Execute allowlisted commands (`ls`, `cat`, `pwd` by default)
- `skills` - Read-only access to skill documentation in `skills/`

Each capability has a `contract()` method describing what it can do and `describe()` for full documentation.

### Direct Use Example - Building a Search Tool

Let's build a utility function in the REPL:

```python
def search_skills(keyword):
    """Search for a keyword across all skills."""
    results = []
    for skill in skills.list():
        name = skill['name']
        content = skills.show(name)
        if keyword.lower() in content.lower():
            results.append(name)
    return results

# Use it
search_skills("harness")  # Returns ['safe-harness', 'harness-debugging']
```

This function persists in the REPL. You can use it in future sessions via `save_state()` / `restore_state()`.

### Agent Use Example - Same Workflow via MCP

An agent would accomplish the same via MCP tools:

```json
// Agent calls execute() tool
{
  "code": "def search_skills(keyword):\n    results = []\n    for skill in skills.list():\n        name = skill['name']\n        content = skills.show(name)\n        if keyword.lower() in content.lower():\n            results.append(name)\n    return results"
}

// Later, agent uses the function
{
  "code": "search_skills('harness')"
}
```

The agent builds up state incrementally through multiple `execute()` calls, just like a human working in the REPL.

## Advanced Workflow - Composing Capabilities

The real power comes from composing capabilities and building domain-specific tools.

### Scenario: Code Analysis Pipeline

**Goal**: Build a pipeline that finds Python files, extracts docstrings, and generates a summary.

**Human Direct Use:**

```python
import re

def extract_docstrings(file_path):
    """Extract docstrings from a Python file."""
    content = fs.read_file(file_path)
    pattern = r'"""(.*?)"""'
    return re.findall(pattern, content, re.DOTALL)

def analyze_codebase(pattern="*.py"):
    """Find Python files and extract their docstrings."""
    # Use cmd to find files
    result = cmd.execute(f"find . -name '{pattern}'")
    if result.get('stdout'):
        files = result['stdout'].strip().split('\n')

        analysis = {}
        for f in files:
            try:
                docs = extract_docstrings(f)
                if docs:
                    analysis[f] = docs
            except:
                pass
        return analysis
    return {}

# Run the analysis
results = analyze_codebase("*.py")
```

**Agent Use:**

The agent would build this incrementally through multiple `execute()` calls, inspecting state between steps:

```json
// Step 1: Define helper
{"code": "import re\n\ndef extract_docstrings(file_path):\n    ..."}

// Step 2: Check it works
{"code": "extract_docstrings('example.py')"}

// Step 3: Build pipeline
{"code": "def analyze_codebase(pattern='*.py'):\n    ..."}

// Step 4: Use state() to verify
// Returns: {functions: [{name: "extract_docstrings", ...}, {name: "analyze_codebase", ...}]}

// Step 5: Run analysis
{"code": "analyze_codebase()"}

// Step 6: Save for later
// Uses save_state() MCP tool
```

## Dynamic Capability Installation

Agents can install new MCP servers at runtime to extend functionality.

### Direct Use - Installing a Capability

From the REPL, you can't install capabilities directly (that requires MCP calls), but you can inspect what's installed:

```python
# List current capabilities
import json
caps = [{'name': c.name, 'type': type(c).__name__} for c in globals().values()
        if hasattr(c, 'name') and hasattr(c, 'describe')]
print(json.dumps(caps, indent=2))
```

### Agent Use - Installing MCP Servers

An agent can dynamically install capabilities:

```json
// Install filesystem capability for a different root
{
  "tool": "install_capability",
  "arguments": {
    "name": "project_fs",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/project"]
  }
}

// Now use it
{
  "tool": "execute",
  "arguments": {
    "code": "files = project_fs.list_directory('src')"
  }
}
```

This enables agents to:
- Connect to project-specific file systems
- Add email, calendar, or database access
- Integrate with web APIs via custom MCP servers
- Build multi-capability workflows on the fly

## State Persistence

State snapshots capture the entire REPL environment.

### What Gets Saved

- **Functions**: Source code, signatures, docstrings
- **Variables**: Serializable values (dill-based pickling)
- **Capabilities**: Native capability source + relay capability connection commands
- **History**: Code execution history

### Direct Use

```python
# After building your tools
state.save("analysis_tools")

# Later session
state.restore("analysis_tools")
# Your functions and data are back!
```

### Agent Use

```json
// Save state
{
  "tool": "save_state",
  "arguments": {"name": "my_checkpoint"}
}
// Returns: {success: true, summary: {functions: 5, variables: 3, ...}}

// List saved states
{
  "tool": "list_saved_states"
}
// Returns: {states: ["default", "my_checkpoint", "analysis_tools"]}

// Restore
{
  "tool": "restore_state",
  "arguments": {"name": "my_checkpoint"}
}
// Returns: {success: true, summary: {functions_restored: 5, ...}}
```

This enables:
- **Session continuity**: Pick up where you left off
- **Checkpointing**: Save before risky operations
- **Sharing**: Export/import REPL environments between agents

## MCP Server Auto-Install

The harness can auto-install MCP servers from `mcp.json` at startup.

### Setup

Create `mcp.json` in your project root (Claude Code format):

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "${HOME}/projects"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "experimental": {
      "command": "python",
      "args": ["-m", "my_custom_server"],
      "disabled": true
    }
  }
}
```

Environment variables like `${HOME}` and `${GITHUB_TOKEN}` are expanded from the shell environment.

### Usage

Start the harness (auto-install enabled by default):

```bash
export GITHUB_TOKEN="ghp_..."
uv run run-harness
```

Servers marked `"disabled": false` are skipped. Disable auto-install entirely with `--no-mcp-config`.

### Verification

From an attached REPL:

```python
# List installed capabilities
import json
caps = [{'name': c.name} for c in globals().values()
        if hasattr(c, 'name') and hasattr(c, 'describe')]
print(json.dumps(caps, indent=2))
```

Or via agent MCP call:

```json
{
  "tool": "list_capabilities"
}
// Returns: [{name: "fs", type: "native", ...}, {name: "github", type: "relay", ...}]
```

## Skills - Progressive Knowledge Disclosure

Skills provide structured documentation that agents discover progressively.

### Skill Structure

```
skills/
  safe-harness/
    SKILL.md           # Main skill content with YAML frontmatter
  harness-debugging/
    SKILL.md
  quick-ref.md         # Single-file skill
```

### Direct Use - Skill Discovery

```python
# List all skills with metadata
all_skills = skills.list()

# Search for relevant skills
def find_skill(keyword):
    for skill in skills.list():
        if keyword in skill.get('description', '').lower():
            return skill['name']
    return None

# Show a skill
skill_name = find_skill('debugging')
print(skills.show(skill_name))

# Unix-style search
cmd.execute("grep -r 'attach' skills/")
```

### Agent Use - Progressive Disclosure

Agents start broad and narrow down:

```json
// Step 1: Discover what skills exist
{"tool": "execute", "arguments": {"code": "skills.list()"}}

// Step 2: Search for relevant topic
{"tool": "execute", "arguments": {
  "code": "[s for s in skills.list() if 'debug' in s.get('description', '').lower()]"
}}

// Step 3: Read specific skill
{"tool": "execute", "arguments": {"code": "skills.show('harness-debugging')"}}
```

This prevents flooding context with all documentation upfront.

## Advanced Configuration

### Custom Command Allowlist

Extend commands for specific workflows:

```bash
# Allow git, ripgrep, and Python execution
uv run run-harness --allow-cmd git --allow-cmd rg --allow-cmd python3
```

The `cmd` capability validates path arguments against allowed paths to prevent escaping the sandbox.

### Custom Safe Root

Change the sandboxed filesystem root:

```bash
uv run run-harness --safe-root /tmp/my_sandbox --no-seed
```

Use `--no-seed` to skip pre-populating example files.

### Logging for Production

Capture detailed logs for debugging agent workflows:

```bash
# Log to file with timestamp
AGENTSELF_LOG_LEVEL=DEBUG uv run run-harness \
  --log-level debug \
  2>&1 | tee "_tmp/logs/$(date +%Y%m%d-%H%M%S)-harness.log"
```

Logs include:
- Every `execute()` call with code snippets
- Capability method calls (fs reads, cmd executions)
- MCP relay traffic to backend servers
- State save/restore operations

### Multiple Attach Clients

Humans can monitor agent activity in real-time:

```bash
# Terminal 1: Agent uses MCP
# (agent connected via stdio)

# Terminal 2: Human monitors
uv run attach-repl --wait  # Blocks until REPL is free
```

Only one client executes at a time, but attach waits politely.

## Troubleshooting

### Agent Can't Execute Code

**Symptom**: Agent's `execute()` calls fail or return errors

**Debug steps**:
1. Check logs: `grep "execute" harness.log`
2. Verify syntax: Try the code in an attached REPL
3. Check state: Use `state()` MCP tool to inspect what's defined
4. Reset if corrupted: Use `reset()` MCP tool

### Capability Installation Fails

**Symptom**: `install_capability()` returns `{success: false}`

**Common causes**:
- MCP server command not found (check PATH)
- Environment variables not expanded (verify in mcp.json)
- Server crashes on startup (check stderr logs)
- Name collision (capability already installed)

**Solution**:
```bash
# Test MCP server manually
npx -y @modelcontextprotocol/server-filesystem /tmp
# Should start without errors

# Check expanded env vars
echo $GITHUB_TOKEN  # Should not be empty
```

### State Restore Fails Partially

**Symptom**: `restore_state()` reports some failures

**Explanation**: This is normal for:
- Non-serializable variables (lambdas, file handles)
- MCP servers that can't reconnect (offline, auth expired)

**Solution**: Check the `summary` field in restore response:
```json
{
  "success": true,
  "summary": {
    "functions_restored": 5,
    "functions_failed": [],
    "relay_failed": [{"name": "github", "error": "connection timeout"}]
  }
}
```

Manually reinstall failed relay capabilities if needed.

### Attach Client Hangs

**Symptom**: `uv run attach-repl` hangs without prompt

**Solutions**:
- REPL is busy: Use `--wait` or wait for agent to finish
- Socket permissions: Check `ls -l _tmp/agentself/repl.sock`
- Stale socket: Remove socket and restart harness

### Permission Denied in Safe Mode

**Symptom**: `fs.write_file()` or `cmd.execute()` fails with permission error

**Explanation**: Safe mode is read-only by design.

**Solutions**:
- For writes: Use a different profile or custom config
- For commands: Add to allowlist with `--allow-cmd`
- For paths: Verify target is within allowed_paths

## Real-World Use Cases

### Use Case 1: Iterative Code Generation

Agent generates and tests code iteratively:

```json
// Generate function
{"tool": "execute", "arguments": {"code": "def parse_csv(path): ..."}}

// Test it
{"tool": "execute", "arguments": {"code": "parse_csv('test.csv')"}}
// Returns error

// Fix and retry
{"tool": "execute", "arguments": {"code": "def parse_csv(path): ... # fixed version"}}

// Save working version
{"tool": "save_state", "arguments": {"name": "csv_parser_v1"}}
```

### Use Case 2: Multi-Step Research

Agent builds knowledge progressively:

```json
// Step 1: List skills
{"tool": "execute", "arguments": {"code": "skills.list()"}}

// Step 2: Read relevant skill
{"tool": "execute", "arguments": {"code": "skills.show('bootstrap-repl')"}}

// Step 3: Extract key info
{"tool": "execute", "arguments": {
  "code": "architecture = {'mcp_tools': [...], 'capabilities': [...]}"
}}

// Step 4: Build summary function
{"tool": "execute", "arguments": {"code": "def summarize(): return architecture"}}
```

### Use Case 3: Capability Composition

Agent combines multiple MCP servers:

```json
// Install file access for project A
{"tool": "install_capability", "arguments": {
  "name": "project_a", "command": "npx -y @modelcontextprotocol/server-filesystem /project/a"
}}

// Install file access for project B
{"tool": "install_capability", "arguments": {
  "name": "project_b", "command": "npx -y @modelcontextprotocol/server-filesystem /project/b"
}}

// Compare projects
{"tool": "execute", "arguments": {"code": `
def compare_structures():
    a_files = project_a.list_directory('.')
    b_files = project_b.list_directory('.')
    return {'a': a_files, 'b': b_files}
`}}
```

## Architecture Philosophy

agentself is built on these principles:

### Runtime-First

The REPL runtime is primary; source files are a serialization format. This inverts the traditional model where files are truth. Here, the live environment is truth, and state snapshots are just exports.

### Capability-Based Security

Capabilities are unforgeable object references with contracts. Instead of call-by-call proxies, capabilities declare what they can do upfront, enabling:
- Pre-approval rather than constant permission prompts
- Derivable capabilities (narrow a filesystem capability to a subdirectory)
- Composition (combine capabilities into higher-level tools)

### Homoiconicity

Code, data, prompts, workflows, and knowledge share the same representation (Python objects). This enables:
- Agents that read and modify their own tools
- Runtime introspection of capabilities
- Seamless mixing of code and data

### Progressive Disclosure

Skills and capabilities are discovered incrementally rather than dumped upfront. Agents:
- List what's available
- Search for relevance
- Load details on demand

This keeps context focused and enables scaling to large knowledge bases.

## Next Steps

### For Human Operators

- Explore `docs/INDEX.md` for complete documentation
- Read `docs/specs/bootstrap-repl.md` for architecture details
- Check `docs/runbooks/safe-harness.md` for operational procedures
- Create custom skills in `skills/` (see `docs/usage/skills.md`)

### For Agent Developers

- Review MCP tool signatures in `src/agentself/harness/server.py`
- Understand relay capabilities in `docs/specs/agent-architecture.md`
- Study state persistence format in `src/agentself/harness/state.py`
- Build custom MCP servers to extend capabilities

### For Researchers

- Explore capability model in `docs/decisions/0002-skills-readonly-access.md`
- Study image vs source models in `docs/specs/agent-architecture.md`
- Consider self-modification workflows in `docs/specs/self-modification.md`
- Review open questions in `docs/OPEN_ISSUES.md`

## Summary

agentself provides a persistent Python REPL with:
- **Dual interfaces**: Direct attach for humans, MCP tools for agents
- **Capability-based security**: Scoped access with explicit contracts
- **State persistence**: Save/restore entire environments
- **Dynamic extension**: Install MCP servers at runtime
- **Progressive disclosure**: Skills discovered incrementally

The same REPL serves both human exploration and agent automation, enabling collaborative workflows where humans monitor, debug, and guide agent activity in real-time.
