# agentself Tutorial

Welcome to agentself, a capability-based REPL harness for coding agents. This tutorial will guide you through setup, basic usage, and common workflows.

## What is agentself?

agentself provides a sandboxed Python REPL environment where coding agents can safely execute code with scoped capabilities. Think of it as a secure workspace where agents can:

- Execute Python code in a persistent session
- Access files and run commands within defined boundaries
- Discover and use skills progressively
- Integrate with MCP servers for extended functionality

## Prerequisites

- Python 3.11 or higher
- `uv` package manager

## Installation

Clone the repository and install dependencies:

```bash
git clone <repository-url>
cd agentself
uv sync
```

## Quick Start

### 1. Start the Harness

The harness runs a persistent Python REPL with safe defaults. Open a terminal and start it:

```bash
uv run run-harness
```

You should see output indicating the harness is running. The harness uses:
- A safe profile with read-only filesystem access
- Command allowlist (`ls`, `cat`, `pwd` by default)
- Socket at `_tmp/agentself/repl.sock` for client connections

**Tip**: Keep this terminal open. The harness runs in the foreground so you can monitor its activity.

### 2. Attach to the REPL

In a new terminal, connect to the running harness:

```bash
uv run attach-repl
```

You should see a Python prompt (`>>>`). You're now connected to the safe REPL!

**Input tips:**
- Press **Enter** to submit when input is complete
- Press **Esc+Enter** to insert a newline for multi-line code
- Use standard readline shortcuts for editing

### 3. Try Basic Commands

Let's explore what's available:

```python
# Check available capabilities
dir()
```

You should see `fs`, `cmd`, `skills`, and `state` objects.

## Working with Capabilities

### Filesystem (fs)

The `fs` capability provides scoped file access:

```python
# List files (read-only in safe mode)
fs.read_file("README.md")

# Check what paths are allowed
fs.contract()
```

In safe mode, `fs` is read-only and scoped to `_tmp/agentself/sandboxes/safe`.

### Command Line (cmd)

The `cmd` capability runs allowlisted shell commands:

```python
# Run allowed commands
cmd.execute("ls")
cmd.execute("pwd")

# Check what's allowed
cmd.contract()
```

By default, only `ls`, `cat`, and `pwd` are allowed. You can extend this with `--allow-cmd` flags when starting the harness:

```bash
uv run run-harness --allow-cmd echo --allow-cmd grep
```

### Skills

The `skills` capability provides read-only access to skill documentation:

```python
# List available skills
skills.list()

# Show a specific skill
skills.show("safe-harness")

# Get the path to a skill
skills.path("safe-harness")

# List files in a skill
skills.files("safe-harness")
```

Skills live in the `skills/` directory and can be either:
- A directory with `SKILL.md` inside
- A single `.md` file with YAML frontmatter

## State Management

The REPL maintains persistent state across executions:

```python
# Define variables or functions
my_data = {"count": 0}

def increment():
    my_data["count"] += 1
    return my_data["count"]

# View current state
state.get()

# Save a named snapshot
state.save("checkpoint1")

# Restore later
state.restore("checkpoint1")
```

## Common Workflows

### Exploring Skills

Skills provide progressive disclosure of knowledge. Use Unix tools for quick searches:

```python
# Search across all skills
cmd.execute("grep -r 'harness' skills/")

# List skill structure
cmd.execute("ls -R skills/")
```

Or use the skills API for structured access:

```python
# Get all skill metadata
all_skills = skills.list()

# Find skills by name
for skill in all_skills:
    if "debug" in skill.get("name", "").lower():
        print(skills.show(skill["name"]))
```

### Working with MCP Servers

The harness can auto-install MCP servers from `mcp.json` (Claude Code format):

1. Create or edit `mcp.json` in your project root
2. Add server configurations (environment variables like `${API_KEY}` are expanded)
3. Restart the harness (auto-install happens at startup)
4. Access MCP tools through installed capabilities

Disable auto-install with `--no-mcp-config` if needed.

### Logging and Debugging

Enable detailed logging to troubleshoot issues:

```bash
# Method 1: Environment variable
AGENTSELF_LOG_LEVEL=DEBUG uv run run-harness

# Method 2: Command-line flag
uv run run-harness --log-level debug

# Method 3: Log to file with timestamps
LOG_FILE="_tmp/logs/$(date +%Y%m%d-%H%M%S)-harness.log"
uv run run-harness 2>&1 | tee "$LOG_FILE"
```

Debug logs include:
- REPL code executions
- Capability calls (fs/cmd operations)
- MCP relay traffic

### Syncing Skills to Agent Directories

If you're developing skills for use with external agents (Claude Code, Gemini CLI):

```bash
uv run sync-agent-skills
```

This copies skills from `skills/` to `.agent/skills/` and creates symlinks in `.claude/skills/`, `.gemini/skills/`, etc.

## Advanced Usage

### Custom Command Allowlist

Extend the allowed commands for specific workflows:

```bash
uv run run-harness --allow-cmd git --allow-cmd rg --allow-cmd python3
```

### Multiple Attach Sessions

You can attach multiple clients simultaneously (read-only). However, only one client can submit code at a time:

```bash
# Terminal 1
uv run attach-repl

# Terminal 2 (will wait if terminal 1 is busy)
uv run attach-repl --wait
```

### Plain Mode

If you prefer basic readline over `prompt_toolkit`:

```bash
uv run attach-repl --plain
```

## Troubleshooting

### Connection Refused

**Symptom**: `ConnectionRefusedError` when attaching

**Solution**: The harness isn't running or crashed. Check:
1. Is the harness terminal still active?
2. Check log files for error messages
3. Restart the harness

### Permission Errors

**Symptom**: Permission denied writing to safe root

**Solutions**:
- The default `_tmp/agentself/sandboxes/safe` should be writable
- Use `--no-seed` to skip pre-seeding files
- Check directory permissions

### Socket Already in Use

**Symptom**: Socket exists but connection fails

**Solution**: Stale socket from previous session. Remove it:

```bash
rm _tmp/agentself/repl.sock
```

Then restart the harness.

### Attach Client Refuses Connection

**Symptom**: "REPL is busy" message

**Solution**: Another client is actively using the REPL. Either:
- Wait for it to finish
- Use `--wait` flag to block until available
- Kill the other client

## Next Steps

- **Read the docs**: See `docs/INDEX.md` for comprehensive documentation
- **Explore capabilities**: Check `docs/usage/capabilities.md` for detailed capability behavior
- **Create skills**: See `docs/usage/skills.md` for skill authoring guidelines
- **Review specs**: Understand the architecture in `docs/specs/bootstrap-repl.md`

## Philosophy

agentself prioritizes:
- **Simplicity**: Keep it simple and nimble
- **Homoiconicity**: Code, data, prompts, workflows, and knowledge as unified representations
- **Self-modification**: The agent can read and write itself (future goal)

## Getting Help

- Check `docs/OPEN_ISSUES.md` for known issues and ongoing work
- Review session summaries in `docs/sessions/` for recent changes
- Inspect runbooks in `docs/runbooks/` for practical procedures

Happy coding!
