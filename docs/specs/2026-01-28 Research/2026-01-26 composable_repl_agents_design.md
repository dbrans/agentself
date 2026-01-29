# Composable REPL Agents: Design Document

**Project**: REPL-first agent framework prototype  
**Status**: Ready for implementation  
**Goal**: Validate object-passing subagents as composable computation units

---

## Premise

Modern coding agents (Claude Code, Cursor) are **tool-orchestrators**: the LLM invokes predefined tools via JSON schemas. This works but limits expressiveness.

**Alternative**: The LLM's only interface is a Python REPL. Everything—including spawning subagents—is just Python code.

---

## Core Concepts

### 1. REPL as Universal Interface

The agent writes Python that executes immediately. State persists across iterations.

```python
import pandas as pd
df = pd.read_csv("data.csv")
summary = df.describe()
RETURN(summary)  # Return result to caller
```

### 2. Subagents Return Objects

A subagent is an isolated REPL that runs its own iteration loop and returns a Python object.

```python
data = spawn("load and clean the dataset", env={"url": url})
model = spawn("train a classifier", env={"data": data})
accuracy = model.score(test_X, test_y)
RETURN(accuracy)
```

Not strings. Actual Python objects.

### 3. Unified `env` Dict

Everything the child needs goes in one dict. No distinction between "data" and "capabilities."

```python
result = spawn(
    "analyze the data",
    env={"df": dataframe, "config": settings, "spawn": spawn, "RETURN": RETURN},
    docs={"df": "Sales data, 10k rows"},
    model="claude-3-haiku",
)
```

### 4. Vanilla Python Semantics

Objects pass by reference (Python's default). Mutations propagate.

```python
my_list = [1, 2, 3]
spawn("append 4", env={"data": my_list})
print(my_list)  # [1, 2, 3, 4] — mutated by child
```

Want isolation? Pass a copy: `env={"data": data.copy()}`.

---

## API

### `spawn()`

```python
def spawn(
    task: str,
    env: dict = None,
    docs: dict = None,
    model: str = "default",
) -> Any:
    """
    Create a subagent to perform a task.
    
    Args:
        task: Natural language description of the task
        env: Variables injected into subagent's namespace
        docs: Descriptions for env variables (for LLM context)
        model: LLM model for this subagent
    
    Returns:
        The value passed to RETURN() by the subagent
    """
```

### `RETURN()`

```python
def RETURN(value: Any) -> NoReturn:
    """Terminate agent and return value to parent."""
```

### `spawn_async()` (Phase 2)

```python
def spawn_async(task: str, env: dict = None, ...) -> Handle:
    """Spawn in background, return handle."""

class Handle:
    def wait(self) -> Any: ...
    def ready(self) -> bool: ...
```

---

## How the Agent Discovers Its Environment

The system prompt includes a summary built from `env` and `docs`:

```
You are in a Python REPL. Your namespace contains:
  df: Sales data, 10k rows
  config: dict
  spawn(): Create a subagent for subtasks
  RETURN(): Return result to caller

Task: "analyze the data"

Write Python code to accomplish the task.
```

For functions, docstrings are extracted automatically. For data, use the `docs` parameter.

---

## Architecture

```
┌───────────────────────────────────┐
│         spawn(task, env)          │
└───────────────────────────────────┘
                 │
                 ▼
┌───────────────────────────────────┐
│            Agent                  │
│  ┌─────────────────────────────┐  │
│  │           REPL              │  │
│  │  namespace = env.copy()     │  │
│  │  + spawn, RETURN injected   │  │
│  └─────────────────────────────┘  │
│                                   │
│  Iteration Loop:                  │
│    1. Build prompt (task + env)   │
│    2. LLM generates code          │
│    3. Execute in REPL             │
│    4. If RETURN called → done     │
│    5. Else → append output, loop  │
└───────────────────────────────────┘
                 │
                 ▼
           RETURN(result)
                 │
                 ▼
         Return to caller
```

---

## Prototype Scope

### Week 1: Core

| Component | Description |
|-----------|-------------|
| `REPL` | Namespace, execute, capture output |
| `Agent` | Wraps REPL + LLM, iteration loop |
| `spawn()` | Create child agent, return object |
| `RETURN()` | Terminate and return value |
| Demo | Data pipeline with 3 subagents |

### Week 2: Expansion

| Component | Description |
|-----------|-------------|
| `spawn_async()` | Background execution |
| `Handle` | Wait, ready, cancel |
| Timeouts | Max iterations, wall-clock limit |
| Error propagation | Child exceptions surface to parent |

---

## File Structure

```
repl-agents/
├── repl_agents/
│   ├── repl.py       # REPL class
│   ├── agent.py      # Agent + iteration loop
│   ├── spawn.py      # spawn(), RETURN(), Handle
│   └── llm.py        # LLM backend
├── examples/
│   ├── data_pipeline.py
│   └── parallel_analysis.py
└── tests/
```

---

## Appendix: Design Decisions

### D1: Single `env` dict vs separate `args`/`capabilities`

**Decision**: Single unified `env` dict.

**Why**: In Python, everything is an object. A function in `env` is indistinguishable from data with methods. The distinction between "data" and "capabilities" is conceptual, not technical. Keeping one dict is simpler and more Pythonic.

---

### D2: Pass-by-reference (Python default) vs copy-by-default

**Decision**: Use Python's default pass-by-object-reference.

**Why**: 
- Familiar to Python developers
- Avoids copy overhead for large objects
- Explicit `data.copy()` when isolation is needed
- Matches how `multiprocessing`, threads, and function calls work

**Prior art**: Ray, Dask, and Celery all let the user decide when to copy.

---

### D3: No wrapper types (Mutable/Immutable/Shared)

**Decision**: No special wrapper types. Just Python objects.

**Why**: Wrappers add API surface without solving real problems. If you want immutability, pass an immutable object or a copy. If you want shared mutation, pass the object directly. Python's semantics are sufficient.

---

### D4: Environment documentation via `docs` dict

**Decision**: Separate `docs` dict + automatic docstring extraction.

**Why**:
- Functions self-document via `__doc__`
- Data needs explicit documentation (no introspectable description)
- Keeps `env` clean (no wrapper objects)
- Fallback to `type(obj).__name__` if no docs provided

---

### D5: `RETURN()` instead of `FINAL()`

**Decision**: Name the termination function `RETURN()`.

**Why**: Frames subagents as functions. `spawn()` calls a subagent; `RETURN()` returns from it. This metaphor is intuitive to programmers and reinforces that subagents return objects, not strings.

---

### D6: Per-agent model selection

**Decision**: Each `spawn()` can specify its own `model`.

**Why**: Different tasks need different models. A quick data-cleaning task might use Haiku; a complex reasoning task might use Opus. This is more flexible than a global model setting.

---

### D7: Hybrid environment discovery (prompt + help)

**Decision**: Include summary in system prompt; `help()` available for details.

**Why**: 
- Summary keeps the LLM informed without bloating the prompt
- `help()` allows deeper exploration if needed
- Scales to many env variables without overwhelming context

---

### D8: Files as paths, accessed by basename

**Decision**: Files parameter takes paths; child accesses by basename in its working directory.

**Why**: Simple mental model. Parent says "these files are available." Child uses them by name. Implementation can copy or symlink as appropriate.
