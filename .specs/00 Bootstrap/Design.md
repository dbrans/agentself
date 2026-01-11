# Agent Interface Paradigms: From REPL to Self-Development

## Context: How This Exploration Began

This document captures a deep exploration of coding agent architectures, starting from analysis of **agentlib** (a REPL-first agent framework) and building toward a design for **self-developing agents**.

### The Starting Point: Agentlib's REPL-First Approach

Agentlib (`/Users/dbrans/Code/agentlib`) takes a fundamentally different approach to coding agents than terminal-based tools like Claude Code or gemini-cli:

- **Terminal-first agents**: LLM orchestrates discrete tool calls (JSON schemas, validated parameters)
- **REPL-first agents**: LLM writes Python code that executes in a persistent subprocess

**Key architectural insight from agentlib**: The LLM "lives inside" a Python REPL. Code is the native output, not JSON tool calls. State persists across turns. Tools are just Python functions.

### The Questions That Drove This Exploration

1. **What are the pros/cons of REPL-first vs terminal-first?** (Philosophical and practical)
2. **What would a more mature REPL-first agent look like?** (Problems to avoid, new advantages)
3. **How could reactive notebook concepts (marimo) inform agent design?**
4. **Where does FastMCP fit in this discussion?**
5. **How does all this inform approaches to self-developing coding agents?**
6. **For self-developing agents: Image model (Smalltalk) or Source model (files)?**

### Key Decisions Made

- **Selected approach**: Hybrid (runtime-primary with dehydration to source files)
- **Core insight**: Most frameworks assume source files define the agent. A self-developing agent inverts this—runtime is primary, source files are a serialization format.

---

## REPL-First vs Terminal-First: Initial Analysis

### Pros of REPL-First (agentlib approach)

1. **Cognitive Alignment**: LLMs trained on billions of lines of Python. Native idiom.
2. **State Persistence**: Variables, functions survive across turns. No "where did I put that value?"
3. **Eliminates Schema Friction**: Just call `glob("*.py")` instead of JSON tool call ceremony.
4. **Composability**: `[read(f) for f in glob("*.py")[:5]]` — one turn, not five tool calls.
5. **Richer Error Context**: Python tracebacks vs. exit code 1.
6. **True Collaboration**: User can drop into same REPL (`/repl` command).
7. **Syntax Error Handling**: Auto-retry without polluting conversation history.
8. **Mid-Conversation Abstraction**: Define helper functions, use them later.

### Cons of REPL-First

1. **Subprocess Complexity**: IPC, signal handling, process isolation.
2. **Python Lock-in**: `cargo build` routes through Python—feels unnatural for polyglot work.
3. **Security Surface**: Arbitrary code execution larger than constrained tool calls.
4. **Context Window Consumption**: `print(df.describe())` can dump hundreds of lines.
5. **Model Dependency**: Not all models equally Python-fluent.
6. **Debugging Opacity**: Bidirectional IPC harder to debug than request/response.
7. **Environment Brittleness**: Python versions, dependencies, platform differences.
8. **Auditability Trade-offs**: Stream of code/output harder to audit than discrete tool calls.

### The Philosophical Divide

**Terminal-first**: LLM as **orchestrator** — plans and coordinates discrete actions.
**REPL-first**: LLM as **programmer** — writes code in a live environment, tight feedback loop.

This reflects different views of intelligence:
- Tool-based: Intelligence as planning and delegation
- REPL-based: Intelligence as direct manipulation and experimentation

---

## Honest Assessment: What's Novel vs. Synthesis

### Probably NOT Novel
- REPL vs terminal comparison — obvious once you see agentlib
- State persistence being useful — well understood
- "Versioning is good" — standard wisdom
- Dependency tracking — people have thought about this

### Potentially Novel or Underexplored

1. **"REPL as MCP server that grows"** — Agent doesn't just consume tools, it IS a server that self-extends. Most MCP discourse assumes agents call out to servers.

2. **"Opaque runtime self" as specific failure mode** — REPL-first agents have a live self but can't easily see that self. Must introspect to understand own structure.

3. **Blast radius awareness** — Agent explicitly knows "if I change X, these things break." Not just dependency tracking for correctness, but as cognitive aid for decision-making.

### What This Document Is
Primarily **useful framing and synthesis**, not a breakthrough invention. The most interesting seed is the MCP server inversion and the hybrid dehydration model.

---

## Part 0: The Deeper Question — Image vs Source

### Two Models of Self-Modifying Systems

**Smalltalk Image Model:**
- The running system IS the source of truth
- "Source code" is derived from the image, not vice versa
- Self-modification = mutate the live image
- Persistence = snapshot the image
- Versioning = image snapshots (hard to diff, hard to merge)
- Transmission = send the image
- **Philosophy**: The living system is primary; text is just a view

**Source File Model:**
- Files on disk are the source of truth
- Running system is instantiated FROM files
- Self-modification = edit source files, then reload/restart
- Persistence = the files themselves
- Versioning = git (diffable, reviewable, mergeable)
- Transmission = share files
- **Philosophy**: Text is primary; the running system is ephemeral

### What Agentlib Currently Does

Based on codebase exploration, agentlib sits awkwardly between these models:

| Component | Where It Lives | Mutable at Runtime | Persistable |
|-----------|---------------|-------------------|-------------|
| System prompt | Memory (conversation[0]) | ✓ | ✓ (via save_session) |
| Tool implementations | Class methods | ✓ (monkey-patch) | ✗ |
| Tool schemas | Metaclass registry | ✗ | ✗ |
| Conversation history | Memory | ✓ | ✓ (JSON) |
| REPL state | Subprocess | ✓ | ✗ |
| Mixin composition | Class definition | ✗ | ✗ |
| Agent class itself | Source files | ✗ | ✓ (it's just files) |

**The gap**: An agent can modify its runtime behavior (monkey-patch tools, change system prompt), but these changes are lost on restart. The only way to persist changes is to edit source files—but then you need to restart.

### The Three Approaches to Self-Modification

#### Approach A: Pure Image (Smalltalk-style)

```
Agent runs → Modifies itself in memory → Snapshots image → Restores from image
```

**Would require:**
- Full agent serialization (not just conversation)
- Serialize tool implementations (code as data)
- Serialize REPL subprocess state
- Image diff/merge tools

**Advantages:**
- Seamless live modification
- No restart friction
- State continuity

**Disadvantages:**
- Hard to review changes (what changed between image v3 and v4?)
- Hard to merge (two agents diverged, how to combine?)
- Opaque to external tools (git doesn't understand images)

#### Approach B: Pure Source (Traditional)

```
Agent runs → Edits its own source files → Restarts → New agent instance
```

**Would require:**
- Agent understands its own source structure
- Agent can generate valid source from intent
- Hot-reload or graceful restart mechanism
- State migration (conversation history survives restart)

**Advantages:**
- Standard tooling (git, diff, code review)
- Clear audit trail
- Mergeable, shareable

**Disadvantages:**
- High friction (restart required)
- State discontinuity (REPL state lost)
- Agent must understand Python source manipulation

#### Approach C: Hybrid (Dehydrate/Rehydrate)

```
Agent runs → Modifies in memory (fast) → "Commits" to source files → Optionally hot-reloads
```

**The key insight**: Separate **working state** from **canonical state**.

- **Working state**: Live runtime modifications (experimental)
- **Canonical state**: Source files (durable, versionable)
- **Commit operation**: Dehydrate working state to canonical state
- **Hot-reload**: Rehydrate canonical state without full restart (where possible)

**Would require:**
1. **Dehydration**: Generate source code from runtime state
   - Tool implementations → method definitions
   - System prompt → attribute or method
   - Dynamic tools → registered tool definitions

2. **Selective hot-reload**:
   - Some components can reload (tool implementations, system prompt)
   - Some require restart (mixin composition, class structure)

3. **State migration**:
   - Conversation history preserved across reload
   - REPL state checkpointed and restored

### What Self-Modification Actually Means

For an agent to "write itself to disk for versioning and transmission":

**The Minimal Version:**
```python
class SelfModifyingAgent:
    def commit_changes(self):
        """Write current state to source files."""
        # 1. Generate source for modified tools
        for name, impl in self._modified_tools.items():
            source = self._dehydrate_tool(name, impl)
            self._write_to_source_file(source)

        # 2. Generate source for system prompt changes
        if self._system_modified:
            self._write_system_prompt_to_source()

        # 3. Git commit
        self._git_commit("Agent self-modification")

    def _dehydrate_tool(self, name, impl):
        """Convert runtime tool to source code."""
        # This is the hard part - going from runtime → source
        return inspect.getsource(impl)  # Only works for some cases
```

**The Hard Problems:**
1. **Runtime → Source translation**: How do you turn a monkey-patched method back into source?
2. **Closure capture**: If the tool references variables from its closure, those need to be captured
3. **Dynamic dependencies**: If the tool was defined based on runtime state, how to reproduce?
4. **Schema generation**: Tool schemas are generated at class-definition time; how to update?

### The Novel Insight

**Most agent frameworks assume the agent is defined by source files.** The running agent is disposable; restart from source.

**A self-developing agent inverts this.** The running agent is primary; source files are a serialization format for versioning and transmission.

This is the Smalltalk philosophy applied to agents—but with a crucial addition: **the ability to dehydrate to diffable, mergeable source files**.

---

## Part 1: A More Mature REPL-First Coding Agent

### Problems in Current REPL-First Approaches (agentlib) That Could Be Avoided

**1. Opaque Runtime State**
The agent must actively introspect (`dir()`, `inspect.getsource()`) to understand what's currently defined. There's no "table of contents" for the REPL's state. A mature implementation would maintain and expose a **live symbol table** showing all defined functions, classes, and variables with their types and origins.

**2. Linear, Append-Only History**
Each turn appends to history. The agent can't say "actually, let me redo turn 3 differently." Current workaround: redefine everything from scratch. A mature implementation would support **non-destructive editing of historical turns** with replay.

**3. Context Window Pollution**
Verbose outputs (DataFrames, tracebacks, logs) consume tokens. Current mitigation: truncation to temp files. Better: **semantic summarization** of outputs. Instead of 500 lines of DataFrame, the agent sees: `DataFrame[1000 rows × 15 cols]: sales data, numeric columns [revenue, quantity], categorical [region, product]`.

**4. No Dependency Tracking**
If the agent redefines `helper_function()`, it has no idea what else might break. A mature implementation would track **which definitions depend on which**, warning: "Redefining `process()` will invalidate `analyze()` and `report()`."

**5. Subprocess Debugging Opacity**
When something goes wrong in the ToolREPL subprocess, debugging is hard. The IPC layer obscures what's happening. A mature implementation would have **better observability**: structured logs, state snapshots, replay capability.

**6. All-or-Nothing Tool Injection**
Tools are either injected (fast, runs in subprocess) or relayed (flexible, IPC overhead). A mature implementation might support **lazy injection**: relay by default, inject on first use if the function is pure.

### New Advantages a Mature REPL-First Agent Could Offer

**1. Computed Context Summaries**
Instead of raw conversation history, provide computed summaries: "You've defined 5 functions, loaded 2 DataFrames, the last error was X." This is **meta-cognition support**.

**2. Speculative Execution**
"What if I changed X?" → Fork the REPL, try it, report results, discard fork. **Safe exploration** without polluting the main state.

**3. Rich Output Integration**
Plots, tables, images rendered and described. The agent doesn't see `<Figure at 0x...>`, it sees the actual visualization (multimodal) or a semantic description.

**4. Persistent Sessions Across Conversations**
Save/restore REPL state between conversations. The agent picks up where it left off. **Continuity of self.**

**5. Multi-REPL Environments**
Separate REPLs for different concerns: one for data exploration, one for tool development, one for testing. **Cognitive separation** that mirrors how humans organize work.

**6. Native Undo/Checkpoint**
`checkpoint("before risky change")` → try something → `restore("before risky change")`. Built into the paradigm, not bolted on.

---

## Part 2: Reactive Notebook Concepts Applied to Agents

### Key Marimo Concepts

1. **Static dependency analysis**: The system knows which cells reference which variables without executing them
2. **Automatic cascade**: Changing a cell re-runs all dependents
3. **No hidden state**: Deleting a cell removes its variables
4. **Lazy evaluation option**: Mark as stale instead of auto-running
5. **Deterministic order**: Execution follows the DAG, not position
6. **Immutable-style updates**: No mutation tracking, create new variables

### How These Could Inform Agent Design

**1. Dependency-Aware Context**
Instead of linear conversation history, the agent sees a **dependency graph**:
```
[data_loading] → [preprocessing] → [analysis] → [visualization]
                         ↓
                   [validation]
```
The agent knows: "If I change preprocessing, analysis, visualization, and validation all need re-evaluation."

**2. Selective Re-Execution**
When the agent modifies something, it can choose:
- **Eager**: Cascade now, see all effects
- **Lazy**: Mark dependents stale, defer execution
- **Selective**: Only cascade through certain paths

This gives the agent **control over the blast radius** of changes.

**3. Cell-Level Versioning**
Each logical unit (cell) has version history. The agent can:
- Compare versions: "What changed between v2 and v5 of the analysis cell?"
- Revert selectively: "Go back to v3 of preprocessing, keep everything else"
- Branch: "Try two different approaches to analysis, compare results"

**4. Structured Self-Representation**
The DAG IS the agent's working memory, made explicit. Instead of implicit state buried in a subprocess, the structure is a first-class object the agent can reason about.

**5. Constraint-Driven Modularity**
Marimo's "no mutation" constraint forces functional decomposition. For agents, this could mean: **each capability is a cell**, with explicit inputs and outputs. Self-modification becomes: edit the cell that defines the capability.

**6. Reproducibility by Construction**
Because execution order follows dependencies (not history), the same DAG always produces the same result. **Determinism** that terminal agents struggle to achieve.

### The Translation to Agent Terms

| Marimo Concept | Agent Equivalent |
|----------------|------------------|
| Cell | Logical unit of computation (could span multiple "turns") |
| Variable | Named result that other computations can reference |
| Dependency | "This computation uses the result of that computation" |
| Stale | "This result may be invalid because an upstream changed" |
| Re-execute | Re-run computation with current inputs |
| DAG | The agent's "working memory structure" |

---

## Part 3: Where FastMCP Fits In

### FastMCP's Core Insight

FastMCP's philosophy: **decorator-based tool definition with minimal ceremony**.

```python
@mcp.tool
def search_files(pattern: str) -> list[str]:
    """Find files matching pattern."""
    return glob.glob(pattern)
```

That's it. The function signature becomes the schema. The docstring becomes the description. No separate JSON schema, no registration boilerplate.

### Relevance to REPL-First vs Terminal-First

**Terminal-first agents** typically consume MCP tools as external services. The tools exist outside the agent, accessed via protocol.

**REPL-first agents** could **define tools at runtime** using FastMCP-style decoration:

```python
# In the REPL, the agent writes:
@tool
def custom_analyzer(data: DataFrame) -> dict:
    """Analyze data using domain-specific logic I just figured out."""
    return {...}

# Now custom_analyzer is available as a tool
```

This is **self-programming via tool definition**. The agent extends its own capabilities by writing decorated functions.

### The Deeper Connection: REPL as MCP Server

What if the agent's REPL **is** an MCP server?

- Tools defined in the REPL become available via MCP
- Other agents (or the same agent in a different context) can call them
- The REPL's state is the server's state
- Self-programming = defining functions that become tools

This inverts the typical relationship. Instead of "agent calls external MCP servers," it's "agent IS an MCP server that grows."

### FastMCP + Reactive = Composable Self-Development

Combine:
1. **FastMCP**: Define tools via decoration
2. **Reactive model**: Track dependencies between tools
3. **REPL environment**: Live definition and testing

Result: The agent can define a tool, see what depends on it, modify it, watch the cascade, and expose it to other agents—all in a live environment.

---

## Part 4: Implications for Self-Developing Coding Agents

### What "Self-Development" Requires

A self-developing agent must:
1. **Perceive its own capabilities**: What can I do?
2. **Identify gaps**: What can't I do that I need to?
3. **Create new capabilities**: Write code that extends myself
4. **Integrate capabilities**: Make new code available for use
5. **Evaluate changes**: Did the new capability work?
6. **Persist or revert**: Keep good changes, discard bad ones

### How Each Paradigm Supports This

#### Terminal/File Approach

```
Perceive: Read my source files
Identify gaps: Compare task requirements to available functions
Create: Write new function to a file
Integrate: Import the new module (restart required)
Evaluate: Run tests
Persist/Revert: Git commit or git checkout
```

**Strengths**: Clear audit trail, standard tooling, language-agnostic
**Weaknesses**: High friction, cold restart required, "self" is inert between runs

#### REPL Approach

```
Perceive: dir(), inspect.getsource()
Identify gaps: Compare task requirements to defined functions
Create: def new_function(): ...
Integrate: Immediate (it's just defined)
Evaluate: Call it, see what happens
Persist/Revert: Re-execute history, or lose it
```

**Strengths**: Immediate feedback, natural Python, low ceremony
**Weaknesses**: Opaque state, no dependency tracking, weak persistence

#### Reactive Notebook Approach

```
Perceive: View the DAG of cells
Identify gaps: See which cells are stale or missing
Create: New cell with new capability
Integrate: Automatic (dependencies resolved)
Evaluate: Cascade shows effects
Persist/Revert: Cell versioning, branch/merge
```

**Strengths**: Structural visibility, predictable changes, native versioning
**Weaknesses**: Novel paradigm (LLM training mismatch), functional constraints

#### Hybrid: Reactive REPL + FastMCP

```
Perceive: Live symbol table + dependency DAG + tool registry
Identify gaps: Compare available tools to task requirements
Create: @tool-decorated function in REPL
Integrate: Automatic (decorator registers, dependencies tracked)
Evaluate: Cascade through dependents, test in isolated fork
Persist/Revert: Cell versioning + checkpoint/restore
```

**This hybrid offers**:
- REPL's cognitive alignment and immediacy
- Reactive model's structural visibility and predictability
- FastMCP's clean tool definition
- First-class versioning and safe exploration

### The Critical Insight: Representation Determines Capability

The format in which an agent represents "itself" determines what self-modifications are tractable:

| Representation | Easy Modifications | Hard Modifications |
|----------------|-------------------|-------------------|
| Files on disk | Add new files, edit text | Change running behavior, maintain state |
| Runtime state | Redefine functions, update variables | Understand structure, track dependencies |
| DAG of cells | Edit cells, watch cascade, version | Novel concepts LLM may not grok |
| Tool registry | Add/remove tools, change schemas | Deep behavioral changes |

**The most powerful self-development comes from combining representations**:
- DAG for structure (what exists, what depends on what)
- Runtime for immediacy (try it now, see what happens)
- Tool registry for capability (what can I do, what can I expose)
- File persistence for durability (survive restarts, share with others)

---

## Part 6: Capability-Based Sandboxed Agent

### The Core Insight: Constrained Power

The previous sections explored REPL-first agents in the context of existing tools like agentlib. But what if we went further? What if we designed an agent architecture from first principles with **security and capability control** as the primary concerns?

**The core constraint:**
> The agent lives inside a very locked-down Python REPL. No access to the file system or the network. Just primitives and a few libraries.

This is a deliberate inversion of typical agent design. Most agents start with full access and try to constrain behavior via prompts or guardrails. Here, we start with **nothing** and explicitly grant capabilities.

---

### The Capability Protocol

A capability is more than a collection of methods—it's a **runtime object** with a well-defined interface:

```python
class Capability(Protocol):
    """The contract all capabilities must fulfill."""

    name: str
    """Unique identifier for this capability."""

    description: str
    """Human-readable description."""

    def describe(self) -> str:
        """Self-documenting interface showing all available methods."""
        ...

    def contract(self) -> CapabilityContract:
        """Declare what side effects this capability might produce."""
        ...

    def derive(self, restrictions: Restrictions) -> 'Capability':
        """Create a more restricted version of this capability."""
        ...
```

**The essential distinction from other abstractions:**

| Concept | Essential Nature |
|---------|-----------------|
| **MCP Tool** | A *remote procedure* — stateless, external, called via protocol |
| **Claude Skill** | A *prompt template* — instructions that shape behavior |
| **Capability** | A *runtime object* — stateful, composable, revocable, in-process |

Capabilities are **objects in the agent's memory**, not external services or static instructions. This enables:
- **Composition**: `SecureFileCap(base_cap, allowed_paths=[...])`
- **Revocation**: `del file_cap` removes access
- **Evolution**: Capability objects can update themselves during a session

---

### Capability Contracts

The **contract** is how a capability declares what it *might* do, enabling pre-approval without runtime proxying:

```python
@dataclass
class CapabilityContract:
    """What a capability declares it might do."""

    reads: list[str] = field(default_factory=list)
    """Resources this capability might read (e.g., ["file:*.py", "env:HOME"])"""

    writes: list[str] = field(default_factory=list)
    """Resources this capability might modify (e.g., ["file:src/*"])"""

    executes: list[str] = field(default_factory=list)
    """Commands/actions this capability might execute (e.g., ["shell:git *"])"""

    network: list[str] = field(default_factory=list)
    """Network resources accessed (e.g., ["https://api.example.com/*"])"""

    spawns: bool = False
    """Whether this capability might create sub-capabilities or agents."""
```

**Why contracts matter**: The two-phase proxy model (execute with proxies, then re-execute for real) has a fundamental flaw—code with control flow depending on capability results can't be accurately recorded. Contracts solve this by letting capabilities declare upfront what they *might* do, enabling **contract-based approval** rather than call-by-call approval.

---

### Capability Taxonomy

**Core Capabilities:**

| Capability | Description | Contract Summary |
|------------|-------------|-----------------|
| **Self-Source** | Read, modify, and experiment with own live source | reads: `["self:*"]`, writes: `["self:staged/*"]` |
| **User Communication** | Communicate with the user | reads: `[]`, writes: `["user:output"]` |
| **File System** | Read, write files and directories | reads/writes: configurable paths |
| **Command Line** | Execute shell commands | executes: configurable command patterns |
| **Capability Loader** | Discover and install other capabilities | spawns: `true` |
| **Task Tracking** | Track agent tasks and progress | writes: `["session:tasks"]` |

**Advanced Capabilities:**

| Capability | Description | Contract Summary |
|------------|-------------|-----------------|
| **Sub-Agents** | Spawn and coordinate child agents | spawns: `true`, inherits parent contracts |
| **Parallel Execution** | Run multiple capability invocations in parallel | inherits from composed capabilities |
| **Capability Factory** | Create new capabilities at runtime | spawns: `true`, writes: `["capabilities:*"]` |

---

### Permission Strategies

Not one model fits all contexts. Multiple permission strategies, selected per-capability or per-session:

| Strategy | When to Use | User Experience |
|----------|-------------|-----------------|
| **Pre-approved** | User trusts this capability entirely | No prompts, all calls allowed |
| **Contract-based** | User approves the contract upfront | One-time approval, calls matching contract auto-allowed |
| **Call-by-call** | High-risk operations, untrusted capabilities | Each invocation prompts for approval |
| **Budget-based** | Limit scope without constant prompting | "You can write up to 10 files" — depleting budget |
| **Audit-only** | High-trust contexts, post-hoc review | Execute immediately, log for review |

```python
class PermissionStrategy(Enum):
    PRE_APPROVED = "pre_approved"
    CONTRACT_BASED = "contract_based"
    CALL_BY_CALL = "call_by_call"
    BUDGET_BASED = "budget_based"
    AUDIT_ONLY = "audit_only"
```

**The two-phase model** (proxy-first) is the implementation of `CALL_BY_CALL`. For most use cases, `CONTRACT_BASED` is the sweet spot—approve what a capability *can* do, not every individual call.

---

### The Bootstrapping Problem: CapabilityLoader

If the agent starts with *nothing*, how does it get capabilities?

The **CapabilityLoader** is a meta-capability that's always present—the minimal trusted base:

```python
class CapabilityLoader(Capability):
    """The one capability that exists from the start.

    Analogous to a kernel—it mediates access to everything else.
    """

    name = "loader"
    description = "Discover and install capabilities into the sandbox."

    def list_available(self) -> list[CapabilityManifest]:
        """What capabilities can be installed?"""
        ...

    def describe_available(self, name: str) -> CapabilityContract:
        """Get the contract for a capability before installing."""
        ...

    def install(
        self,
        name: str,
        restrictions: Restrictions | None = None,
    ) -> Capability:
        """Install a capability (requires user approval of its contract).

        Returns the installed capability object.
        """
        ...

    def uninstall(self, name: str) -> bool:
        """Remove a capability from the environment."""
        ...

    def list_installed(self) -> list[str]:
        """What capabilities are currently installed?"""
        ...
```

**The approval flow for installing a new capability:**

```
Agent: loader.install("web_fetch")
        ↓
System: Show user the contract for web_fetch:
        "WebFetchCapability requests:
         - network: https://*
         - reads: response bodies
         Approve? [y/n/restrict]"
        ↓
User: "y" (or configures restrictions)
        ↓
System: Capability installed, available as `web` in sandbox
```

---

### Self-Development via Capabilities

The **CapabilityFactory** is where self-improvement meets the capability model:

```python
class CapabilityFactory(Capability):
    """Create new capabilities at runtime.

    The agent can extend itself by writing new capabilities.
    """

    name = "factory"
    description = "Create and test new capabilities."

    def create(self, name: str, source: str) -> str:
        """Stage a new capability from source code.

        The capability is compiled and validated but not yet installed.
        """
        ...

    def test(self, name: str) -> TestResult:
        """Test a staged capability by instantiating it."""
        ...

    def install(self, name: str) -> Capability:
        """Install a staged capability into the sandbox."""
        ...

    def commit(self, name: str) -> str:
        """Persist a capability to disk for future sessions."""
        ...
```

**The self-development loop:**

1. Agent encounters a problem it can't solve with existing capabilities
2. Agent uses `factory.create()` to write a new capability
3. Agent uses `factory.test()` to verify it works
4. Agent uses `factory.install()` to make it available in the current session
5. Agent uses `factory.commit()` to persist it for future sessions

```python
# Example: Agent creates a domain-specific capability
factory.create("json_schema", '''
class JsonSchemaCapability(Capability):
    """Validate JSON against schemas."""

    name = "json_schema"
    description = "Validate JSON data against JSON Schema specifications."

    def validate(self, data: dict, schema: dict) -> ValidationResult:
        """Validate data against a JSON schema."""
        import jsonschema  # Available in sandbox's allowed imports
        try:
            jsonschema.validate(data, schema)
            return ValidationResult(valid=True)
        except jsonschema.ValidationError as e:
            return ValidationResult(valid=False, error=str(e))
''')

factory.test("json_schema")  # Verify it works
factory.install("json_schema")  # Now available as `json_schema` in sandbox
factory.commit("json_schema")  # Saved to src/agentself/capabilities/json_schema.py
```

---

### Capability Packaging and Distribution

For the **marketplace vision**—capabilities that can be published, discovered, and installed:

```
capability-package/
├── manifest.yaml          # Metadata, dependencies, contract
├── capability.py          # The implementation
├── tests/                 # Verification tests
└── README.md              # Documentation
```

**manifest.yaml:**
```yaml
name: web_fetch
version: 1.2.0
author: example@example.com
description: Fetch and parse web content

contract:
  network:
    - "https://*"
    - "http://*"
  reads:
    - "response:body"
    - "response:headers"

dependencies:
  - httpx>=0.24.0

permissions:
  minimum: contract_based
  recommended: pre_approved
```

**Trust model for distributed capabilities:**
- **Signed by author** (identity verification)
- **Verified by registry** (safety scan, contract accuracy)
- **Reputation score** (community trust)
- **Permission audit** (what it declares vs. what it does)

---

### Relationship to Existing Standards

**How capabilities relate to MCP, Claude Skills, and plugins:**

| Aspect | Capabilities | MCP | Claude Skills |
|--------|-------------|-----|---------------|
| **Runtime nature** | In-process objects | External servers | Prompt templates |
| **State** | Can maintain state | Stateless calls | No runtime state |
| **Security model** | Contract + permission strategy | Trust the server | Prompt guardrails |
| **Composition** | First-class (wrap, derive) | Independent servers | Independent skills |
| **Evolution** | Can modify during session | Static per connection | Static definitions |
| **Self-creation** | Agent can create new ones | No | No |

**Capabilities are a superset**: MCP servers can be wrapped as capabilities. Skills can initialize capability configurations. The permission model can layer atop MCP connections.

---

### Honest Limitations

**The proxy model's fundamental constraint:**

```python
# This can't be accurately recorded in proxy mode:
if fs.exists(path):
    content = fs.read(path)
    process(content)
```

If `exists()` returns nothing in proxy mode, execution can't continue. If it returns mock `True`, you get a different path than if it returns `False`.

**Solutions we're exploring:**
1. **Contract-based approval** — Approve what a capability *can* do, not each call
2. **Speculative execution** — Fork sandbox, run both branches, record both
3. **Symbolic values** — Track which paths depend on capability results
4. **Accept the limitation** — Call-by-call only for straight-line code

**What this architecture can't do well:**
- Capabilities with complex internal state that can't be easily serialized
- Operations that require true atomicity across multiple capability calls
- Ultra-low-latency scenarios (permission checking adds overhead)

---

### Design Principles

1. **Deny by Default**: The sandbox starts empty. Every capability is an explicit grant.

2. **Contracts Over Proxies**: Capabilities declare what they *might* do. Approve contracts, not individual calls.

3. **Self-Documenting**: Each capability can describe itself. The agent doesn't need external documentation.

4. **Composable and Derivable**: `fs.derive(read_only=True)` creates a restricted version.

5. **Revocable**: Removing a capability object removes access. No residual permissions.

6. **Self-Extensible**: The agent can create new capabilities via CapabilityFactory.

7. **Packageable**: Capabilities can be versioned, signed, and distributed.

---

### Open Questions (Refined)

1. **Contract verification**: How do we ensure a capability's actual behavior matches its declared contract?

2. **Capability versioning**: When a capability updates, how do existing approvals translate?

3. **Cross-agent delegation**: Can an agent pass a restricted version of its capability to a sub-agent?

4. **Capability conflict**: What if two capabilities have overlapping contracts?

5. **Offline capabilities**: Can capabilities work without network access to the registry?

6. **Audit and compliance**: How do we generate audit logs for regulated environments?

---

## Synthesis: Design Principles for Self-Developing Agents

### 1. Make Structure Explicit
The agent should see its own structure, not have to reconstruct it via introspection. A DAG, symbol table, or tool registry—something the agent can read directly.

### 2. Support Non-Destructive Exploration
Speculative execution, branching, checkpointing. The agent should be able to try things without fear of breaking its current state.

### 3. Track Dependencies
When the agent modifies something, it should know what else might be affected. Cascading or staleness marking—either way, the blast radius is visible.

### 4. Enable Live Capability Definition
FastMCP-style decoration: write a function, it becomes a capability. Minimal ceremony between "I need this" and "I have this."

### 5. Version Everything
Cell-level, function-level, session-level versioning. The agent can compare, revert, branch, merge. Self-development is an iterative process.

### 6. Maintain Cognitive Alignment
Despite adding structure, stay close to how LLMs think. Python over novel DSLs. Explicit over magical. The structure should help the LLM, not confuse it.

---

## Conclusion

**REPL-first** (agentlib) is a significant advance over terminal-first because it treats the LLM as a programmer in a live environment, not an orchestrator of discrete tools.

**Reactive notebooks** (marimo) offer a structural model—the DAG—that makes state visible, changes predictable, and versioning natural.

**FastMCP** provides the ceremony-free tool definition that makes self-programming practical: write a function, decorate it, it's a capability.

**For self-developing agents**, the synthesis is:
- A REPL for cognitive alignment and immediacy
- Reactive concepts for structural visibility and dependency tracking
- FastMCP-style decoration for capability self-definition
- First-class versioning for safe exploration

The unexplored frontier is an agent interface that combines all four: a **versioned, dependency-aware, live-programming environment** where the agent can see its own structure, extend its own capabilities, and safely explore modifications.

---

## Part 5: Concrete Implementation — Hybrid Self-Modifying Agent

### What Can Be Hot-Reloaded vs. Requires Restart

| Component | Hot-Reloadable | Mechanism |
|-----------|---------------|-----------|
| Tool implementations | ✓ | Update `_toolimpl` dict, re-inject into REPL |
| Tool schemas | ✓ | Already lazy via `regen_toolspec` callbacks |
| System prompt | ✓ | Update `conversation.messages[0]` |
| Mixin composition | ✗ | MRO fixed at class creation |
| Class structure | ✗ | Requires new class + state transfer |

### The Dehydration/Commit Workflow

```
Agent experiments at runtime
         ↓
+------------------+
| modify_tool()    |  ← Runtime modification
| system = "..."   |  ← In-memory change
+------------------+
         ↓
+------------------+
| Test in REPL     |  ← Agent runs with new behavior
+------------------+
         ↓
+------------------+
| commit_changes() |  ← Dehydrate to source
+------------------+
         ↓
+-----------------------------------+
| 1. ChangeTracker.get_changes()   |
| 2. SourceGenerator.generate()    |
| 3. ast.parse() validation        |
| 4. Write to _generations/v{N}.py |
| 5. git commit (optional)         |
+-----------------------------------+
         ↓
+------------------+
| Source files now |
| canonical form   |
+------------------+
```

### Minimal Viable Implementation

**New files to add:**
```
src/agentlib/self_modify/
    __init__.py          # Export SelfModifyingMixin
    tracker.py           # ChangeTracker - tracks what changed
    generator.py         # SourceGenerator - runtime → source
    mixin.py             # SelfModifyingMixin with tools
```

**Core classes:**

```python
# tracker.py
@dataclass
class ToolChange:
    name: str
    original_source: Optional[str]
    current_source: str
    timestamp: float

class ChangeTracker:
    def __init__(self, agent):
        self.baseline = self._snapshot()
        self.changes = {}

    def record_tool_change(self, name, new_impl):
        self.changes[name] = ToolChange(...)

    def get_changes(self) -> AgentChanges:
        return AgentChanges(tools=self.changes, ...)
```

```python
# generator.py
class SourceGenerator:
    def generate_tool_source(self, impl, name) -> str:
        """Convert runtime function to source code."""
        # Leverage existing source_extract module
        from agentlib.tools.source_extract import extract_method_source
        return extract_method_source(impl, name)

    def generate_class_source(self, agent, changes) -> str:
        """Generate complete agent class definition."""
        lines = [f"class {type(agent).__name__}(...):"]
        for name, change in changes.tools.items():
            lines.append("    @BaseAgent.tool")
            lines.append(textwrap.indent(change.current_source, "    "))
        return '\n'.join(lines)
```

```python
# mixin.py
class SelfModifyingMixin:
    def _ensure_setup(self):
        super()._ensure_setup()
        self._tracker = ChangeTracker(self)

    @BaseAgent.tool
    def modify_tool(self, name: str, new_code: str):
        """Modify a tool implementation at runtime."""
        exec_globals = {}
        exec(new_code, exec_globals)
        new_impl = exec_globals.get(name)

        self.__class__._toolimpl[name] = new_impl
        self._tracker.record_tool_change(name, new_impl)

        # Re-inject if REPL agent
        if hasattr(self, '_tool_repl'):
            self._reinject_tool(name, new_impl)

        return f"Tool '{name}' updated. Call commit_changes() to persist."

    @BaseAgent.tool
    def commit_changes(self, message: str = "Commit message"):
        """Persist runtime changes to source files."""
        changes = self._tracker.get_changes()
        if not changes.has_modifications():
            return "No changes to commit"

        source = SourceGenerator().generate_class_source(self, changes)

        # Validate
        ast.parse(source)

        # Write to _generations/
        output = self._get_generations_path()
        output.write_text(source)

        self._tracker.reset_baseline()
        return f"Committed to {output}"
```

### REPL State Preservation

For hot-reload that preserves REPL state:

```python
class REPLStateCapture:
    CAPTURE_CODE = '''
import json, types, inspect
state = {'variables': {}, 'functions': {}, 'imports': []}
for name, value in dict(globals()).items():
    if name.startswith('_'): continue
    if isinstance(value, types.FunctionType):
        try: state['functions'][name] = inspect.getsource(value)
        except: pass
    elif isinstance(value, (int, float, str, bool, list, dict)):
        state['variables'][name] = repr(value)
print(json.dumps(state))
'''

    def capture(self, repl) -> dict:
        output = repl.execute(self.CAPTURE_CODE)
        return json.loads(output.split('\n')[-1])

    def restore(self, repl, state: dict):
        for line in state['imports']:
            repl.execute(line)
        for name, val in state['variables'].items():
            repl.execute(f"{name} = {val}")
        for source in state['functions'].values():
            repl.execute(source)
```

### Self-Awareness Tools

```python
class SelfAwareMixin:
    @BaseAgent.tool
    def read_my_source(self) -> str:
        """Read this agent's source code."""
        return inspect.getsource(type(self))

    @BaseAgent.tool
    def read_tool_source(self, name: str):
        """Read a specific tool's source."""
        impl = self._toolimpl.get(name)
        return inspect.getsource(impl) if impl else f"Not found: {name}"

    @BaseAgent.tool
    def list_my_tools(self) -> List[str]:
        """List available tools."""
        return list(self.toolspecs.keys())
```

### Critical Files to Modify

| File | Purpose |
|------|---------|
| `agent.py` | Understand `_toolimpl`, `_toolspec`, `AgentMeta` |
| `repl_agent.py` | `ToolREPL`, tool injection, REPL state |
| `tools/source_extract.py` | Foundation for `SourceGenerator` |
| `tool_mixin.py` | Pattern for hook-based mixins |

### Extension Points

1. **Commit strategies** - `_generations/`, sibling file, overwrite original
2. **Validation hooks** - Linting, tests, type checking before commit
3. **Version control** - Auto git commit after dehydration
4. **Approval workflow** - Human-in-the-loop before commit
5. **CLI commands** - `/commit`, `/rollback`, `/diff`

---

## Summary: The Novel Contribution

**What's genuinely new here:**

1. **The Hybrid Model** — Neither pure Smalltalk image nor pure source files. Runtime is primary for experimentation; source files are a serialization format for versioning and transmission.

2. **Dehydration as First-Class Operation** — `commit_changes()` as a tool the agent can call, not an external operation performed on the agent.

3. **Self-Awareness Tooling** — `read_my_source()`, `read_tool_source()`, `list_my_tools()` as tools enabling the agent to understand its own structure.

4. **Selective Hot-Reload** — Some components (tools, prompts) reload without restart; others (mixins) require warm restart with state transfer.

5. **REPL State Preservation** — Capture and restore subprocess state across reloads, maintaining continuity.

**The philosophical shift:**

> Most agent frameworks assume the agent is defined by source files. The running agent is disposable—restart from source.
>
> A self-developing agent inverts this. The running agent is primary; source files are a serialization format.

---

## Appendix A: Agentlib Architecture Deep Dive

This section captures the detailed exploration of agentlib's internals that informed the implementation design.

### Core Components

**BaseAgent** (`src/agentlib/agent.py`)
- Metaclass-based tool registry (`AgentMeta`)
- `_toolimpl`: Dict of tool implementations (methods)
- `_toolspec`: Dict of Pydantic models for tool schemas
- Tools registered via `@BaseAgent.tool` decorator

**REPLAgent** (`src/agentlib/repl_agent.py`)
- Replaces tool-calling with code execution
- Manages `ToolREPL` subprocess
- Statement-by-statement execution with output streaming
- Syntax error auto-retry (up to 3 attempts, doesn't pollute history)

**ToolREPL** (`src/agentlib/repl_agent.py`)
- Persistent Python subprocess with bidirectional IPC
- Two tool patterns:
  - **Injected** (`inject=True`): Source extracted, runs in subprocess (zero IPC overhead)
  - **Relay** (default): Stub in subprocess calls back to main process

**Mixin System**
- Capabilities composed via multiple inheritance
- Hook methods chain via `super()`: `_ensure_setup()`, `_build_system_prompt()`, `_handle_toolcall()`, `_cleanup()`
- Key mixins: `MCPMixin`, `CLIMixin`, `JinaMixin`, `SandboxMixin`, `FilePatchMixin`

### File Structure

```
src/agentlib/
├── agent.py              # BaseAgent, AgentMeta, @tool decorator
├── repl_agent.py         # REPLAgent, ToolREPL, REPLMixin
├── conversation.py       # Message history management
├── client.py             # LLMClient (API calls)
├── *_mixin.py            # Capability mixins
├── agents/
│   └── code_agent.py     # CodeAgent (production implementation)
└── tools/
    ├── subrepl.py        # SubREPL subprocess manager
    └── source_extract.py # Extract method source for injection
```

### What Can Be Modified at Runtime

| Component | Runtime Mutable | Persistable | Mechanism |
|-----------|-----------------|-------------|-----------|
| System prompt | ✓ | ✓ (save_session) | `conversation.messages[0]` |
| Tool implementations | ✓ (monkey-patch) | ✗ | Update `_toolimpl` dict |
| Tool schemas | Limited | ✗ | `regen_toolspec` callbacks |
| Conversation history | ✓ | ✓ (JSON) | Direct manipulation |
| REPL state | ✓ | ✗ | Subprocess memory |
| Mixin composition | ✗ | ✗ | MRO fixed at class creation |

### Key Implementation Details

**Tool Registration** (agent.py:38-39):
```python
cls._toolimpl = {}  # name -> implementation
cls._toolspec = {}  # name -> Pydantic schema (or regen callback)
```

**Tool Injection** (source_extract.py):
- Uses `inspect.getsource()` to get method source
- Parses to AST, removes 'self' parameter
- `ast.unparse()` to regenerate clean Python
- Injected into subprocess at startup

**Conversation Persistence** (CodeAgent):
```python
def save_session(self, filename):
    json.dump(self.conversation.messages, open(filename, "w"))

def load_session(self, filename):
    self.conversation.messages = json.load(open(filename))
```

**What's NOT Supported**:
- Dynamic tool schema registration (without MCP pattern)
- Full agent serialization (only messages)
- Dynamic mixin application after class creation
- Modifying MRO at runtime

### The Gap This Reveals

Agentlib is designed for **capability composition** (mixins at class definition) and **runtime behavior modification** (monkey-patching), but NOT for **persistent self-modification**. An agent can modify its runtime behavior, but changes are lost on restart. The only way to persist is to edit source files—requiring restart.

This gap motivates the Hybrid model: runtime modifications for experimentation, dehydration to source files for persistence.

---

## Appendix B: Marimo Reactive Model

Key concepts from marimo that informed the agent design:

**Static Dependency Analysis**: System knows cell dependencies without execution
**Automatic Cascade**: Changing a cell re-runs all dependents
**No Hidden State**: Deleting a cell removes its variables from memory
**Lazy Evaluation**: Can mark cells stale instead of auto-running
**Deterministic Order**: Execution follows DAG, not cell position
**Pure Python Storage**: Notebooks are `.py` files, not JSON (git-friendly)

**Marimo's Constraints**:
- No mutation tracking (must create new variables)
- Each global variable defined by exactly one cell
- Forces functional decomposition

---

## Appendix C: FastMCP Relevance

**FastMCP's Philosophy**: Decorator-based tool definition with minimal ceremony.

```python
@mcp.tool
def search(query: str) -> list[str]:
    """Search for files."""
    return glob.glob(query)
```

Function signature → schema. Docstring → description. No boilerplate.

**Connection to Self-Development**:
- REPL-first agents could use FastMCP-style decoration for runtime tool creation
- The REPL could BE an MCP server that grows
- `@tool` decorator in REPL = self-programming via capability definition

---

## Sources

- [FastMCP GitHub](https://github.com/jlowin/fastmcp) - Pythonic MCP framework
- [Marimo Documentation](https://docs.marimo.io/) - Reactive notebook concepts
- [Google Cloud MCP Announcement](https://cloud.google.com/blog/products/ai-machine-learning/announcing-official-mcp-support-for-google-services) - MCP ecosystem growth

---

## How to Continue This Work

To continue this exploration from this document:

1. **If exploring further**: The key open questions are in "Potentially Novel or Underexplored" section
2. **If implementing**: Start with Part 5's MVP — create `src/agentlib/self_modify/` with tracker, generator, and mixin
3. **If extending the design**: Consider the reactive notebook integration (dependency DAG for agent state)

**The core implementation insight**: Leverage existing `source_extract.py` for dehydration. The hard problem is closure capture and dynamic dependencies.
