# Coding Agent Capability Plan

## Context

The current `agentself` agent implements the **self-modification** paradigm from `SELF_IMPROVING_AGENT_IDEAS.md`:
- Introspect its own tools and source
- Modify tools at runtime
- Persist changes via dehydration to source files

However, it **cannot act as a coding agent for arbitrary Python repositories** because it lacks fundamental capabilities for interacting with external codebases.

This document plans the addition of those capabilities.

---

## Gap Analysis

### What Exists

| Capability | Status | Implementation |
|------------|--------|----------------|
| Self-introspection | ✓ | `list_tools`, `read_my_source`, `read_tool_source` |
| Self-modification | ✓ | `modify_tool`, `add_tool`, `modify_system_prompt` |
| Change tracking | ✓ | `ChangeTracker`, `AgentChanges` |
| Persistence | ✓ | `SourceGenerator`, `commit_changes` |
| LLM integration | ✓ | Claude API with tool use |

### What's Missing

| Capability | Required For |
|------------|--------------|
| File reading | Understanding external code |
| File writing/editing | Making changes to repos |
| Directory listing/globbing | Navigating codebases |
| Code search (grep) | Finding relevant code |
| Shell execution | Running tests, builds, scripts |
| Project understanding | Parsing pyproject.toml, understanding structure |
| Working directory context | Knowing "where" the agent is operating |

---

## Design Principles

### 1. Tool-Based Extension

New capabilities should be added as **tools** using the existing `@tool` decorator pattern. This:
- Maintains the self-modifiable architecture
- Allows the agent to introspect its coding capabilities
- Enables future self-improvement of these tools

### 2. Minimal, Composable Tools

Prefer many small, focused tools over few large ones:
- `read_file` not `read_and_analyze_file`
- `run_command` not `run_test_suite`

The LLM composes these; we provide primitives.

### 3. Safety by Default

The agent should:
- Operate within a configurable working directory
- Refuse or warn on operations outside that directory
- Have configurable "dangerous operation" policies (delete, overwrite, shell exec)

### 4. Homoiconicity Preserved

The coding tools themselves should be:
- Readable by the agent (`read_tool_source("read_file")`)
- Modifiable by the agent (via `modify_tool`)
- Persistable (via `commit_changes`)

The agent can improve its own coding capabilities.

---

## Proposed Tool Set

### Phase 1: File System Primitives

```python
@tool
def read_file(self, path: str) -> str:
    """Read the contents of a file.

    Args:
        path: Absolute or relative path to the file

    Returns:
        File contents as a string, or error message
    """

@tool
def write_file(self, path: str, content: str) -> str:
    """Write content to a file, creating it if it doesn't exist.

    Args:
        path: Path to the file
        content: Content to write

    Returns:
        Success message or error
    """

@tool
def edit_file(self, path: str, old_text: str, new_text: str) -> str:
    """Replace text in a file.

    Args:
        path: Path to the file
        old_text: Exact text to find and replace
        new_text: Replacement text

    Returns:
        Success message showing the change, or error
    """

@tool
def list_directory(self, path: str = ".") -> str:
    """List contents of a directory.

    Args:
        path: Directory path (default: current working directory)

    Returns:
        Formatted list of files and directories
    """

@tool
def glob_files(self, pattern: str) -> str:
    """Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.py", "tests/*.py")

    Returns:
        Newline-separated list of matching paths
    """
```

### Phase 2: Code Navigation

```python
@tool
def grep(self, pattern: str, path: str = ".", file_pattern: str = "*.py") -> str:
    """Search for a pattern in files.

    Args:
        pattern: Regex pattern to search for
        path: Directory to search in
        file_pattern: Glob pattern for files to search

    Returns:
        Matches with file:line:content format
    """

@tool
def find_definition(self, symbol: str, path: str = ".") -> str:
    """Find where a symbol (function, class, variable) is defined.

    Args:
        symbol: Name of the symbol to find
        path: Directory to search in

    Returns:
        File and line where the symbol is defined
    """

@tool
def get_file_outline(self, path: str) -> str:
    """Get an outline of a Python file's structure.

    Args:
        path: Path to the Python file

    Returns:
        Outline showing classes, functions, and their signatures
    """
```

### Phase 3: Shell Execution

```python
@tool
def run_command(self, command: str, timeout: int = 30) -> str:
    """Execute a shell command.

    Args:
        command: Command to execute
        timeout: Maximum seconds to wait (default: 30)

    Returns:
        Combined stdout/stderr and exit code
    """

@tool
def run_python(self, code: str) -> str:
    """Execute Python code in a subprocess.

    Args:
        code: Python code to execute

    Returns:
        Output and any errors
    """
```

### Phase 4: Project Understanding

```python
@tool
def get_project_info(self, path: str = ".") -> str:
    """Get information about a Python project.

    Parses pyproject.toml, setup.py, or setup.cfg to extract:
    - Project name and version
    - Dependencies
    - Entry points
    - Python version requirements

    Args:
        path: Project root directory

    Returns:
        JSON-formatted project information
    """

@tool
def get_import_graph(self, path: str = ".") -> str:
    """Map the import relationships in a Python project.

    Args:
        path: Project root directory

    Returns:
        Graph of which modules import which
    """
```

---

## Working Directory Model

The agent needs a concept of "where it is operating":

```python
@dataclass
class Agent:
    # ... existing fields ...
    working_directory: Path = field(default_factory=Path.cwd)

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to working directory."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.working_directory / p

    def _check_path_allowed(self, path: Path) -> bool:
        """Check if path is within allowed boundaries."""
        # Could be configurable: strict (must be under working_dir)
        # or permissive (anywhere readable)
        resolved = path.resolve()
        return resolved.is_relative_to(self.working_directory.resolve())
```

CLI would accept a target directory:

```bash
agentself /path/to/project
```

---

## Safety Considerations

### Path Traversal
- All paths resolved relative to working directory
- Configurable policy for absolute paths and `..` traversal

### Shell Execution
- Timeout on all commands
- Configurable allowlist/blocklist for commands
- Option to require confirmation for destructive commands

### File Operations
- Backup before overwrite (configurable)
- Refuse to overwrite without explicit flag
- Configurable patterns to never modify (e.g., `.git/*`, `node_modules/*`)

### Resource Limits
- Max file size for reading
- Max output size from commands
- Max concurrent operations

---

## System Prompt for Coding Tasks

The default system prompt should change when the agent is pointed at a project:

```python
CODING_SYSTEM_PROMPT = """You are a Python coding assistant working on the project at {working_directory}.

You have tools to:
- Read and write files
- Search code (grep, find_definition)
- Run shell commands
- Understand project structure

When making changes:
1. First understand the existing code
2. Make minimal, focused changes
3. Explain what you're doing and why
4. Test your changes when possible

You can also introspect and modify your own tools if needed.
"""
```

---

## Implementation Phases

### Phase 1: File System (MVP)
- `read_file`, `write_file`, `edit_file`
- `list_directory`, `glob_files`
- Working directory support
- Basic path safety

This alone enables the agent to work on repos, just with raw string matching for code navigation.

### Phase 2: Code Navigation
- `grep`, `find_definition`, `get_file_outline`
- These make the agent much more efficient at understanding codebases

### Phase 3: Shell Execution
- `run_command`, `run_python`
- Enables running tests, builds, scripts
- Requires careful safety design

### Phase 4: Project Intelligence
- `get_project_info`, `get_import_graph`
- Higher-level understanding of Python projects
- Could use AST parsing for accuracy

---

## Integration with Self-Modification

The coding capabilities should be self-modifiable. Example scenario:

1. User asks agent to work on a Django project
2. Agent realizes it doesn't have Django-specific tools
3. Agent uses `add_tool` to create `find_django_views`:
   ```python
   add_tool("find_django_views", '''
   def find_django_views(self, path: str = ".") -> str:
       """Find all Django view functions in a project."""
       # ... implementation using grep + AST parsing ...
   ''')
   ```
4. Agent uses `commit_changes` to persist this new tool
5. Future sessions have Django-specific capabilities

This is the **self-improvement loop** applied to coding capabilities.

---

## Alternative Approaches Considered

### A: Bring in External Tool Library
Could import tools from `agentlib` or similar.

**Rejected because:**
- Adds dependency
- Less homoiconic (can't easily modify external code)
- Harder to understand/debug

### B: REPL-Based File Operations
Use a persistent Python REPL for all operations.

**Rejected because:**
- More complex
- Less direct (file ops through REPL layer)
- Save REPL approach for compute-heavy tasks

### C: MCP Server Integration
Expose tools via MCP, let Claude Code or similar connect.

**Interesting but deferred because:**
- Adds protocol complexity
- Could be Phase 5: make the agent an MCP server

---

## Open Questions

1. **Should file edits be AST-aware?**
   - Pro: More reliable refactoring
   - Con: More complex, Python-specific
   - Tentative: Start with string-based, add AST tools later

2. **How to handle large files?**
   - Chunking? Line ranges? Summarization?
   - Tentative: Return truncated with warning, provide `read_file_lines(path, start, end)` variant

3. **Should there be a "sandbox" mode?**
   - All changes staged, require explicit apply?
   - Tentative: Defer, but design for it

4. **Git integration?**
   - Built-in git tools vs. rely on `run_command`?
   - Tentative: Start with `run_command("git ...")`, add specialized tools if needed

---

## Success Criteria

The agent should be able to:

1. **Navigate**: Given a repo path, explore and understand its structure
2. **Search**: Find relevant code given natural language description
3. **Read**: Read and comprehend files
4. **Edit**: Make targeted changes to files
5. **Validate**: Run tests/linters to verify changes
6. **Explain**: Describe what it did and why

Example workflow:
```
User: Fix the bug in the login function where it doesn't handle empty passwords
Agent:
  1. Uses glob_files("**/*.py") to find Python files
  2. Uses grep("def login", ...) to find login function
  3. Uses read_file(...) to read the relevant file
  4. Uses edit_file(...) to add empty password check
  5. Uses run_command("pytest tests/test_auth.py") to verify
  6. Explains the change
```

---

## Next Steps

1. Implement Phase 1 (file system tools) in `agent.py`
2. Add working directory support
3. Update CLI to accept target directory
4. Update system prompt for coding context
5. Test on a sample Python project
6. Iterate based on findings

---

## Relationship to SELF_IMPROVING_AGENT_IDEAS.md

That document answers: **"How does an agent modify itself?"**

This document answers: **"How does an agent modify external code?"**

The two are complementary:
- Self-modification gives the agent the ability to improve its coding tools
- Coding tools give the agent something to improve (its effectiveness on real tasks)

The vision: An agent that gets better at coding **by coding**, including coding on itself.
