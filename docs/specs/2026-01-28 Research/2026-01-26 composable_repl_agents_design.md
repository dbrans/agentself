# Composable REPL Agents: Design Document v2

**Project**: REPL-first agent framework prototype  
**Status**: Implementation Design  
**Goal**: Build a distributed, recursively self-improving agent system using Actor Model & RLM patterns.

---

## Premise

Traditional agents communicate via strings (chat), creating a bottleneck for heavy data tasks.  
**Redesign**: We move to a **Distributed Actor-REPL** model.
1.  **Agents are Actors**: Long-lived, isolated processes (Ray Actors) that maintain state.
2.  **Communication is Reference-Based**: Agents pass `ObjectRef` handles to shared memory (Plasma Store), not serialized strings.
3.  **Context is Managed**: Using Recursive Language Model (RLM) patterns, context is treated as variable slices in the REPL, not a monolithic prompt.

---

## Core Concepts

### 1. The Actor-REPL
Each agent is an independent "Actor" running a Python REPL. It runs in its own process/container but shares a distributed object store with others.

```python
# Concept
@ray.remote
class AgentActor:
    def __init__(self, env_refs):
        self.repl = REPL()
        self.namespace.update(env_refs) # References to shared objects
```

### 2. Zero-Copy Object Passing
Instead of serializing a 1GB DataFrame to JSON, we put it in the Object Store and pass a small `ObjectRef`.

```python
# Parent
df = pd.read_csv("huge_data.csv")
df_ref = store.put(df)  # Stored in shared memory
sub_agent = spawn("analyze", env={"data": df_ref})

# Child
# 'data' in namespace is a proxy/reference. 
# Child can read it directly (zero-copy) or pass it along.
print(data.shape) 
```

### 3. RLM Context Management
We mitigate context window limits by treating the context as a set of variables.

*   **Prompt**: "You have a dataframe `df` in your environment..."
*   **Action**: Agent inspects `df.head()` locally.
*   **Recursion**: Agent spawns a sub-agent to process a specific row or slice, passing only that slice's reference.

### 4. Agent Contracts (Governance)
Recursion is dangerous. We bound it with **Contracts**.

```python
contract = Contract(
    budget_tokens=100_000,
    timeout_sec=60,
    output_type=AnalysisResult
)
result_ref = spawn("task", contract=contract)
```

---

## API Design

### `spawn()` (Async)

```python
async def spawn(
    task: str,
    env: Dict[str, Any] = None,
    contract: Contract = None,
    files: List[str] = None
) -> ObjectRef:
    """
    Spawns a child Agent Actor.
    
    Args:
        task: Instruction.
        env: Variables (values or ObjectRefs) to inject.
        contract: Resource bounds and type constraints.
    
    Returns:
        ObjectRef resolving to the child's return value.
    """
```

### `store` (Object Store Abstraction)

```python
class ObjectStore:
    def put(self, obj: Any) -> ObjectRef: ...
    def get(self, ref: ObjectRef) -> Any: ...
```

---

## Architecture

```
┌────────────────────────┐          ┌────────────────────────┐
│     Parent Actor       │          │      Child Actor       │
│ ┌────────────────────┐ │  spawn   │ ┌────────────────────┐ │
│ │        REPL        │ ├─────────►│ │        REPL        │ │
│ │ Env: {data: Ref1}  │ │          │ │ Env: {data: Ref1}  │ │
│ └─────────┬──────────┘ │          │ └─────────┬──────────┘ │
└───────────│────────────┘          └───────────│────────────┘
            │                                   │
            │           ┌───────────────────┐   │
            └──────────►│ Distributed Store │◄──┘
                        │    [ Ref1: DF ]   │
                        └───────────────────┘
```

---

## Appendix: Design Decisions

### D1: Ray as Backend
**Decision**: Use **Ray** for the POC.
**Why**: It solves the "hard parts" (Shared Memory, Actors, Serialization) out of the box. We can wrap it to keep our API clean.

### D2: Contract Enforcement
**Decision**: Contracts are enforced by the *Framework*, not the Agent.
**Why**: An agent cannot be trusted to self-terminate. The supervisor (Parent Actor) monitors the contract and kills the Child Actor if limits are exceeded.

### D3: Environment Parity
**Decision**: Sub-agents inherit the Parent's valid environment context (imports/vars) via explicit passing.
**Why**: Explicit passing preventing namespace pollution while allowing RLM-style context slicing.
