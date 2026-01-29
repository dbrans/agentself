# **Architecting Composable Code-Executing Agents: A Deep Analysis of State, Orchestration, and Runtime Environments**

## **Executive Summary**

The paradigm of Large Language Model (LLM) agents is undergoing a fundamental architectural shift. The initial generation of agents—characterized by text-based conversational interfaces and "chat" history as the primary state mechanism—is proving insufficient for complex, multi-step engineering workflows. In these text-centric architectures, inter-agent coordination relies on natural language passing, which introduces significant latency, serialization overhead, and ambiguity.

A new paradigm is emerging: the **REPL-First Agent**. In this model, the agent’s primary interface is not a dialogue box but a code execution environment (Read-Eval-Print Loop). State is maintained not in a context window of past tokens, but in the active memory of a language runtime (e.g., Python, JavaScript). Crucially, this enables **compositionality**: agents can function as computational units that spawn sub-agents, delegate tasks, and receive rich Python objects—such as DataFrames, neural network weights, or active socket connections—rather than serialized text strings.

This research report provides an exhaustive, expert-level analysis of the technologies, frameworks, and theoretical models required to build such a system. It synthesizes insights from nine distinct problem spaces, ranging from distributed object stores and capability-based security models to academic theories on recursive agent composition.

The analysis reveals that while the interface layer for these agents is maturing through tools like Open Interpreter and Claude Code, the backend infrastructure for efficient "object-passing" orchestration is fragmented. Current multi-agent frameworks like AutoGen and LangGraph largely default to string-based communication, failing to leverage the shared-memory patterns pioneered by distributed systems like Ray and Dask. Furthermore, the security landscape presents a dichotomy: container-based solutions (Docker) offer compatibility but suffer from high resource overhead, while emerging WebAssembly (WASI) standards offer granular isolation but lack the mature threading support necessary for complex, hierarchical agent lifecycles.

By examining the convergence of actor models, distributed computing, and recursive language modeling, this report outlines the critical design implications for the next generation of composable, code-executing AI frameworks.

## ---

**Part I: The Rise of REPL-First Agents**

The transition from "Chat-First" to "REPL-First" represents a move from agents that *talk* about work to agents that *perform* work within a verifiable computational substrate. This section analyzes existing systems that pioneer this interface, evaluating their architecture, state persistence mechanisms, and suitability for composition.

### **1.1 Open Interpreter: Local Execution and OS Integration**

Open Interpreter serves as a foundational reference for local, code-executing agent architectures. Unlike cloud-hosted solutions that abstract away the underlying machine, Open Interpreter is designed to interface directly with the user’s local operating system, effectively turning the local shell into an agentic REPL.

#### **Architecture and Streaming Execution**

The core capability of Open Interpreter is its ability to stream code execution. In traditional request-response models, the user waits for the full code block to be generated before execution begins. Open Interpreter implements a streaming architecture where code chunks are parsed and potentially prepared for execution in real-time. This reduces the perceptual latency and allows for more interactive debugging loops.1

The system operates by spawning a local language runtime—typically Python, though it supports JavaScript and shell scripting—and piping the LLM’s output into this runtime. The stdout and stderr are captured and fed back to the model, creating a tight feedback loop. This architecture allows the agent to self-correct; if a library is missing or a syntax error occurs, the error message becomes the prompt for the next turn, enabling the agent to attempt a fix without user intervention.

#### **State Persistence and "OS Mode"**

A critical differentiator for Open Interpreter is its approach to state. In hosted environments like OpenAI’s Code Interpreter, the session is ephemeral; variables and files are lost when the session times out. Open Interpreter, running locally, maintains process persistence. A Pandas DataFrame loaded in the first interaction remains in memory for the duration of the server process. This persistence is a prerequisite for composable agents, as it allows the "state" to be an evolving memory space rather than a static text history.

Furthermore, Open Interpreter’s "OS Mode" extends the REPL concept beyond code. By leveraging a Computer API, the agent can generate events that manipulate the mouse, keyboard, and screen. This effectively treats the Operating System itself as a REPL environment, where the "function calls" are GUI interactions and the "return values" are screenshots or accessibility tree data.2 This expansion of the REPL definition is vital for agents that must interact with legacy software or tools that lack an API.

**Gap Analysis**: While powerful for single-user tasks, Open Interpreter’s architecture is monolithic. It relies on a single process on a single machine. It lacks a native mechanism for an agent to "spawn" a sub-agent in a secure, isolated container. If the main agent runs a destructive command, the host system is compromised. There is no built-in "object passing" mechanism to other agents; communication is strictly strictly through the context window (text/images).

### **1.2 E2B: Sandboxed Environments as an API**

E2B (Everything 2 Backend) addresses the security and isolation deficiencies of local execution by providing code execution environments as a managed cloud service. It introduces the architectural pattern of "Sandboxes as Objects."

#### **The Sandbox Lifecycle**

In the E2B model, a "sandbox" is a discrete entity that can be instantiated, manipulated, and destroyed via an SDK. An agent does not just "run code"; it acquires a CodeInterpreter resource.

* **Long-Lived Sessions**: Crucially, these sandboxes are stateful and persistent. The SDK maintains a "heartbeat" connection (ping) to keep the sandbox alive.3 This allows for a workflow where an agent performs data ingestion in Step 1, pauses for human feedback or external API calls, and then resumes analysis in Step 2, accessing the same variables in memory.  
* **Integration with Agent Frameworks**: E2B integrates with LangChain and other frameworks by exposing the execute function as a "Tool." When an agent invokes this tool, the Python code is transmitted to the cloud sandbox, executed, and the results (stdout, stderr, artifacts) are returned.

#### **Data Exchange Limitations**

Despite its robust isolation (using Firecracker microVMs), E2B currently reinforces the "String-Based" coordination model. Data returned from the sandbox is typically serialized. Standard output is captured as text; images are returned as base64 strings or URLs. There is no direct, shared-memory channel that would allow an agent to pass a reference to a live Python object (like a socket or a loaded model) to another agent running in a different sandbox. The "Object Passing" requirement of the user's framework is not natively satisfied here; it requires an additional layer (like a shared object store) to function effectively.5

### **1.3 Claude Code and Recursive Language Models (RLM)**

Anthropic’s recent work on Claude Code and the associated academic research into Recursive Language Models (RLM) represents the theoretical cutting edge of REPL-first agents. This approach fundamentally reimagines the "Context Window" as a manipulable memory store.

#### **Context as Variables**

The RLM architecture, detailed by Zhang and Khattab, proposes that agents should not view their context as a linear stream of text, but as a set of variables in an environment. In this model, the "prompt" is just one variable. The agent can write code to:

1. **Peek**: Look at specific slices of the context.  
2. **Condense**: Summarize a variable and store the summary in a new variable.  
3. **Delegate**: Pass a variable to a sub-model or sub-agent function.7

#### **Programmatic Decomposition and Recursion**

The most significant innovation in RLM is the use of the REPL to manage recursion. An agent can define a function—effectively a sub-agent—and call it: result \= llm\_query(sub\_prompt, context=variable). The return value of this function is stored in the REPL. This allows for infinite context processing by breaking large tasks into smaller, programmatically managed sub-tasks.

* **Variable Passing**: RLM explicitly supports the concept of "passing variables" rather than "dumping text." The sub-agent returns a value that the parent agent holds as a reference.7 This aligns perfectly with the user's requirement for subagents acting as functions returning objects.  
* **Claude Code Implementation**: In practice, Claude Code implements this by acting as a terminal-integrated agent that builds a "memory" of the codebase it is working on. It performs "deep dives" (recursive analysis) to understand dependencies before modifying code, effectively using the file system and its internal memory map as the "state".10

### **1.4 Jupyter-Based Architectures**

OpenAI’s Code Interpreter (now Advanced Data Analysis) popularized the Jupyter kernel as the agent interface.

* **Visual Feedback**: The strength of the Jupyter model is the rich display protocol. Agents can generate charts, images, and interactive widgets.  
* **Closed System**: However, the OpenAI implementation is a "walled garden." It does not support spawning sub-kernels or exporting state to other agents. The state is trapped within the single session.  
* **Open Source Variants**: Frameworks like jupyter-agent attempt to replicate this by connecting LLMs to local Jupyter servers. While this opens up the environment, it typically lacks the sophisticated orchestration layers (like RLM's recursion) needed for complex multi-agent systems.

### **Summary of Prior Art**

| System | Primary Interface | State Persistence | Sub-Agent Capability | Object Passing Mechanism |
| :---- | :---- | :---- | :---- | :---- |
| **Open Interpreter** | Local Terminal / OS | Process Memory (Local) | No (Monolithic) | N/A (Single Process) |
| **E2B** | Cloud Sandbox SDK | Managed MicroVM | Yes (via separate Sandboxes) | Serialized (JSON/Text/File) |
| **Claude Code (RLM)** | REPL / Terminal | REPL Variables | **Yes (Recursive Calls)** | **Reference/Variable Passing** |
| **OpenAI Interpreter** | Chat w/ Sandbox | Session (Ephemeral) | No | N/A (Closed) |

## ---

**Part II: The Data Bottleneck in Multi-Agent Orchestration**

The core challenge in scaling from a single coding agent to a system of composable agents is **Orchestration**. How do agents coordinate, and more importantly, how do they move data? Current frameworks are largely built on the assumption that agents communicate like humans: via text messages. This creates a severe bottleneck for engineering tasks involving complex data structures.

### **2.1 AutoGen: The Conversable Agent Pattern**

Microsoft’s AutoGen defines agents as "Conversable" entities. The fundamental atomic action is sending a message.

* **Textual Protocol**: Even when an AutoGen agent executes code (via a UserProxyAgent or DockerCommandLineCodeExecutor), the result is captured as a string (the console output) and appended to the chat history. The "Function Call" mechanism relies on the LLM outputting JSON, which is then parsed and executed, with the return value converted back to a string.12  
* **The Serialization Trap**: If Agent A computes a large NumPy array and wants Agent B to analyze it, Agent A must serialize the array (e.g., print it, save it to a CSV) and tell Agent B where to find it. AutoGen does not natively support passing a Python object reference (like a memory pointer) from one agent to another.  
* **Ray Integration**: AutoGen has introduced experimental support for running agents as **Ray Actors**. This allows agents to be distributed across a cluster. However, the communication implementation still largely wraps the textual message protocol inside Ray’s actor calls. It does not fully exploit Ray’s shared memory store for zero-copy data transfer between agents, treating Ray primarily as a deployment mechanism rather than a data plane.14

### **2.2 LangGraph: State Machines and Cyclicity**

LangGraph represents a step forward by formalizing the "State" as a structured object rather than a list of messages.

* **State Schema**: In LangGraph, the graph definition includes a schema (typically a TypedDict or Pydantic model) that defines the structure of the state (e.g., messages, artifacts, errors). This state is passed between nodes (agents).  
* **Object Passing Potential**: Since the state is a Python object, it *can* theoretically hold complex types. However, LangGraph heavily emphasizes state persistence (checkpointing) to support human-in-the-loop workflows and fault tolerance. To be check-pointed, the state must be serializable. This discourages holding raw pointers, sockets, or thread locks in the state.16  
* **Map-Reduce and Send**: LangGraph introduces the Send primitive for map-reduce patterns. A node can generate multiple Send objects, each directing a specific payload to a downstream node. This supports parallel sub-agent execution. Yet, the payload is typically a dictionary of data, again implying serialization if the agents are not in the same memory space.18

### **2.3 The "Object Passing" Gap**

Both AutoGen and LangGraph fail to fully satisfy the requirement of "subagents returning Python objects" in a distributed context.

* **Local Process**: If all agents run in the same Python process, passing objects is trivial (Python does it by reference).  
* **Distributed Process**: As soon as agents run in different processes (essential for sandboxing and parallel scaling), these frameworks default to serialization (Pickle, JSON). This incurs:  
  * **Latency**: Serialization/Deserialization (SerDes) of large data is slow.  
  * **Complexity**: The LLM must write code to save/load data, or the framework must handle it invisibly.  
  * **Fidelity Loss**: Some objects (e.g., a database connection cursor) cannot be serialized.

To solve this, we must look beyond "Agent Frameworks" to "Distributed Computing Frameworks."

## ---

**Part III: Distributed Object Systems (The Solution Layer)**

The user’s requirement—passing Python objects between agents—is a solved problem in the domain of distributed computing. Frameworks like Ray and Dask have engineered sophisticated mechanisms to handle exactly this challenge.

### **3.1 Ray: The Object Store Standard**

**Ray** is the industry standard for distributed Python state management and is the most architecturally aligned with the "Composable Agent" vision.

#### **The Plasma Object Store**

At the heart of Ray is the **Plasma Object Store**, a shared-memory server running on each node in a cluster.

* **Zero-Copy Reads**: When a task (or agent) produces an object (like a large matrix), it is stored in Plasma. If another task on the same node needs to read this object, Ray maps the memory directly into the second task's address space. No CPU cycles are spent copying data. This allows for extremely high-throughput data sharing between agents.19  
* **ObjectRefs**: Ray uses ObjectRef as the universal handle. When an agent calls a remote function (sub-agent), it immediately receives an ObjectRef. This reference can be passed to other agents: agent\_b.process.remote(ref\_from\_agent\_a). The receiving agent does not need to fetch the data until it actually uses it. Ray’s backend ("Raylet") manages the data movement, ensuring the object is available on the node where the task runs.21

#### **Serialization and "Pickle 5"**

Ray addresses the "Pickle Risk" and performance issues using a customized backport of **Pickle Protocol 5**.

* **Out-of-Band Data**: Pickle 5 allows separating the "structure" of an object from its "data buffers" (byte arrays). Ray serializes the structure but leaves the heavy data buffers in the shared memory store. This is what enables the zero-copy capability.  
* **Cloudpickle**: To handle closures, lambda functions, and dynamic classes (common in code generated by LLMs), Ray utilizes cloudpickle, which can serialize a wider range of Python constructs than the standard library pickle.19

#### **The Actor Model**

Ray Actors are stateful workers. An agent in the user’s framework can be mapped 1:1 to a Ray Actor.

* **State Isolation**: Each Actor has its own Python process and memory space.  
* **Method Calls**: Sub-agents are methods on an Actor or new Actors spawned dynamically.  
* **Comparison to Task Graphs**: While Dask builds a graph of "Tasks" (functions), Ray optimizes for "Actors" (services). Since agents maintain state (memory, history, loaded libraries), the Actor model is superior for long-running agentic processes.23

### **3.2 Dask: Futures and Task Graphs**

**Dask** offers a similar but distinct approach.

* **Task Graph**: Dask builds a directed acyclic graph (DAG) of computations. It excels at analytics where the computation is defined upfront or lazily.  
* **Futures**: Like Ray, Dask returns Future objects. These can be passed around.  
* **Scatter**: Dask allows "scattering" local data to the cluster, returning a Future.  
* **Limitation for Agents**: Dask is optimized for data throughput, not actor latency or complex stateful interactions. Its scheduler is centralized, which can become a bottleneck for massive numbers of small, interactive agent steps compared to Ray’s decentralized scheduling.25

## ---

**Part IV: Capability and Permission Models**

Allowing LLM agents to execute code and spawn sub-processes creates immense security risks. A robust framework must restrict *what* the code can do without crippling its ability to function.

### **4.1 WebAssembly (WASI): The Future of Isolation**

**WebAssembly (Wasm)** coupled with **WASI (WebAssembly System Interface)** offers the most promising path for secure, high-performance sandboxing.

#### **Capability-Based Security**

WASI operates on a capability-based security model. A Wasm module cannot open a file, access the network, or read the clock unless it is explicitly granted that "capability" (import) by the host runtime.

* **Fine-Grained Control**: Unlike Docker, where a container usually sees a whole virtual filesystem, WASI allows granting access to specific directories or sockets. This aligns with the "Principle of Least Privilege" required for autonomous agents.27  
* **The Component Model**: The new WASI Component Model allows composing modules written in different languages via high-level interfaces (Records, Lists, Strings). This standardization facilitates the exchange of complex data between sandboxed agents without relying on language-specific serialization like Pickle.29

#### **The Threading Bottleneck**

The major hurdle for Python agents in WASI is **Threading**.

* **WASI-Threads**: The proposal to add threads to WASI is still maturing. Current implementations in runtimes like **Wasmtime** or **WAMR** do not fully support the pthread model required by Python’s multiprocessing or threading modules.  
* **Spawning Sub-Agents**: In a native environment, an agent spawns a sub-agent by forking a process or starting a thread. In WASI, because of the threading limitations, spawning a "sub-agent" often requires the host to spin up a completely new Wasm instance. This increases overhead and complicates shared-memory communication between the parent and child agent.30

### **4.2 Pyodide and In-Process Sandboxing**

**Pyodide** compiles the CPython interpreter to WebAssembly, originally for browser use.

* **Isolation**: Because it runs in Wasm, it is isolated from the host OS.  
* **Sub-Interpreters**: Recent efforts (PEP 684\) are bringing "Per-Interpreter GIL" to Python. This allows multiple Python interpreters to run in the same process with true parallelism. If Pyodide fully supports this, it would allow a single Wasm instance to host a "swarm" of agents in sub-interpreters, sharing memory efficiently.  
* **Current Limitations**: As of now, sharing objects between Pyodide instances requires copying data through the JavaScript (or Rust) host layer, breaking the zero-copy ideal. Furthermore, security vulnerabilities have been found in implementations (like n8n’s use of Pyodide) where the isolation layers were not strictly enforced, allowing sandbox escapes via library imports.32

### **4.3 Docker and Containers**

**Docker** remains the pragmatic industrial standard.

* **Compatibility**: It supports standard Python, C extensions, and threading perfectly.  
* **Overhead**: Containers are heavy. Starting a Docker container takes seconds.  
* **MicroVMs**: Solutions like **Firecracker** (used by E2B and AWS Lambda) bridge the gap. They offer the isolation of a VM with startup times comparable to containers (\~100ms). For a framework where agents spawn sub-agents frequently, Firecracker microVMs are currently the most viable production backend.5

## ---

**Part V: Academic Foundations of Composable Agents**

Academic research provides the theoretical models for how agents can decompose tasks and reason about code.

### **5.1 Code as Policies (CaP)**

The **Code as Policies** paper by Liang et al. is a foundational text for code-executing agents.

* **Hierarchical Generation**: CaP prompts LLMs to generate policy code that controls robots. Crucially, it encourages the model to *recursively define undefined functions*. If the high-level task is arrange\_table(), the code might call move\_object(). The system detects move\_object is undefined and prompts the LLM to write it.34  
* **Object Passing**: The generated code passes rich Python objects—NumPy arrays representing point clouds, Shapely polygons representing obstacles—between functions. It demonstrates that LLMs can effectively reason about and manipulate abstract object handles, not just text descriptions.35

### **5.2 Recursive Language Models (RLM)**

As discussed in Part I, **RLM** formalizes the "Prompt as Environment" concept.

* **Inference-Time Scaling**: RLM shows that you can scale inference compute by allowing the model to decompose a prompt into a tree of sub-prompts.  
* **State Management**: The "REPL" in RLM is the memory controller. It stores the intermediate results of the tree search. This academic work validates the "Context as Variables" architecture.7

### **5.3 Language Agent Tree Search (LATS)**

**LATS** integrates **Monte Carlo Tree Search (MCTS)** into the agent loop.

* **Lookahead and Rollback**: An agent explores a "thought" (a code execution path). If it fails (exception/bad result), it backtracks.  
* **Requirement**: This requires the runtime to support **Checkpointing**. The agent must be able to "fork" the state of the REPL to explore two different branches. This connects directly to the need for copy-on-write filesystems or serializable state objects.37

## ---

**Part VI: Actor Models, Messaging, and Contracts**

To manage the complexity of composable agents, we need rigorous communication protocols.

### **6.1 The Actor Model**

* **Erlang/Elixir**: Pioneers of the "Shared Nothing" architecture. Actors communicate *only* by copying messages. This guarantees fault tolerance (one crashing actor doesn't corrupt another's memory) but is inefficient for large data.39  
* **Akka (Typed)**: Introduces **Typed Messaging**. Actors define a schema for the messages they accept. This is critical for LLM agents, which are prone to "hallucinating" API calls. A typed interface acts as a compile-time (or runtime) guardrail, rejecting invalid commands before execution.41

### **6.2 Agent Contracts**

Recent research on **Agent Contracts** proposes a formal governance layer for agent interactions.

* **The Contract Tuple**: A contract is defined as a tuple ![][image1], where:  
  * ![][image2]: Input/Output specifications (Types).  
  * ![][image3]: Resource constraints (Budget, Tokens, Time).  
  * ![][image4]: Success criteria (Unit tests, Verifiers).  
* **Delegation**: When Agent A spawns Sub-Agent B, it creates a *derived contract*. It delegates a portion of its resource budget (![][image3]) to B. This prevents the "infinite recursion" problem where a sub-agent loop consumes all system resources. The contract enforces that the sub-agent must return a result matching type ![][image5] within time ![][image6].43

## ---

**Part VII: Coordination Primitives**

How do agents coordinate without a central orchestrator?

### **7.1 Blackboard Architecture**

The **Blackboard Pattern** is experiencing a resurgence.

* **Decoupling**: Instead of Agent A calling Agent B directly, Agent A posts a partial solution (an Object) to a shared Blackboard. Agent B, monitoring the board, sees a task it can perform and claims it.  
* **Ray as Blackboard**: In the proposed framework, the **Ray Object Store** acts as the Blackboard. Agents post ObjectRefs to a shared metadata registry. This allows for dynamic, opportunistic coordination—multiple sub-agents can work on the same data in parallel without explicit point-to-point wiring.45

### **7.2 Contract Net Protocol (CNP)**

**CNP** models coordination as a market.

* **Task Announcement**: Agent A announces a task.  
* **Bidding**: Agents B, C, and D bid (e.g., "I can do this in 2s", "I have the data loaded").  
* **Award**: Agent A grants the task to the best bidder.  
* **Relevance**: This is highly relevant for **Tool Selection**. If an agent needs to "Resize Image," multiple sub-agents (one using PIL, one using OpenCV, one using a cloud API) could bid. The manager selects the most efficient one based on the contract.43

## ---

**Part VIII: Industry Practice and Production Systems**

### **8.1 Replit Agent: The Snapshot Engine**

**Replit** has engineered the most sophisticated state management for coding agents.

* **Copy-on-Write Filesystem**: Replit uses a Btrfs-based filesystem that allows instant "Snapshotting" of the entire container.  
* **Speculative Execution**: The agent can create a snapshot, try a code modification, run tests, and if they fail, instantly revert the filesystem to the clean state. This "Undo" capability is essential for autonomous coding, allowing the agent to explore the solution space safely.47  
* **Replspace**: A persistent storage layer that allows file-based state to be shared across sessions, effectively a network-attached object store.49

### **8.2 Devin (Cognition AI)**

**Devin** represents the state-of-the-art in autonomous engineering.

* **The "Planner" Model**: Devin separates the "Planner" (which maintains the high-level plan and reasoning) from the "Executor" (which interacts with the shell/editor).  
* **Long-Term State**: Devin maintains a consistent environment state. It does not "reset" between prompts. It uses the shell history and file system as its long-term memory.  
* **Snapshots**: Like Replit, Devin uses machine snapshots to save the state of the dev environment, allowing it to resume tasks or branch off for experiments.50

## ---

**Part IX: Synthesis and Design Implications**

To satisfy the requirement of "LLM agents executing Python code and spawning subagents that return Python objects," the research points to a specific hybrid architecture.

### **9.1 The "Ray-Agent" Architecture**

Existing "Agent Frameworks" (AutoGen, LangGraph) are insufficient because they lack a distributed shared-memory object store. "Distributed Frameworks" (Ray) are insufficient because they lack the LLM orchestration logic.

**Recommendation**: Build the framework on **Ray**.

* **Agents as Actors**: Implement each agent as a ray.remote Actor. This gives it a persistent process and isolated state.  
* **Object Store for Communication**: Use Ray’s Plasma store. When Agent A spawns Sub-Agent B, B returns an ObjectRef. Agent A’s LLM is prompted to handle this reference string (e.g., \<ObjectRef: 1234\>) as a variable, passing it to subsequent tools or agents.

### **9.2 The "Wasm-Sandbox" Future**

While Ray/Docker is the solution today, **Wasm** is the target.

* **Transition Path**: Design the agent interface using the **WASI Component Model** (even if implemented in Python initially). This prepares the system to swap out Docker containers for Wasm sandboxes once wasi-threads and Pyodide sub-interpreters mature, unlocking millisecond-level agent spawning.

### **9.3 State Management via Snapshots**

Do not rely on the LLM to "remember" state in its context window.

* **System-Level Persistence**: Implement a **Snapshotting** mechanism (like Replit’s) for the underlying container/REPL. If the agent crashes or needs to backtrack (LATS), restore the container snapshot.

### **9.4 Governance via Contracts**

To prevent the chaos of infinite recursive sub-agents:

* **Enforce Contracts**: Wrap every sub-agent spawn in a formal **Agent Contract**. Enforce resource budgets (tokens, RAM) and return types at the runtime level. If a sub-agent violates the contract, the runtime kills it and returns a structured Failure object to the parent, allowing the parent to recover.

### **Comparison Table: Architecture Selection**

| Feature | AutoGen / LangGraph | Ray (Recommended) | WebAssembly / WASI |
| :---- | :---- | :---- | :---- |
| **Primary Unit** | Chat / Node | Actor (Process) | Module / Component |
| **Object Passing** | Serialization (Slow) | **Shared Memory (Zero-Copy)** | Component Model (Typed) |
| **Sub-Agent Spawn** | Function Call | **Remote Actor Spawn** | Instance Instantiation |
| **Isolation** | Process / Container | Process / Worker | **Memory Sandbox** |
| **State** | History / Dict | Actor State | Linear Memory |

This architecture bridges the gap between the linguistic reasoning of LLMs and the rigorous, high-performance world of distributed computing.

#### **Works cited**

1. openinterpreter/open-interpreter: A natural language interface for computers \- GitHub, accessed January 27, 2026, [https://github.com/openinterpreter/open-interpreter](https://github.com/openinterpreter/open-interpreter)  
2. How It's Built: Open Interpreter | Sean Lynch, accessed January 27, 2026, [https://sean.lyn.ch/how-its-built-open-interpreter/](https://sean.lyn.ch/how-its-built-open-interpreter/)  
3. Give LangGraph code execution capabilities — E2B Blog, accessed January 27, 2026, [https://e2b.dev/blog/langgraph-with-code-interpreter-guide-with-code](https://e2b.dev/blog/langgraph-with-code-interpreter-guide-with-code)  
4. e2b-cookbook/examples/langgraph-python/langgraph\_code\_interpreter.ipynb at main, accessed January 27, 2026, [https://github.com/e2b-dev/e2b-cookbook/blob/main/examples/langgraph-python/langgraph\_code\_interpreter.ipynb](https://github.com/e2b-dev/e2b-cookbook/blob/main/examples/langgraph-python/langgraph_code_interpreter.ipynb)  
5. Build AI data analyst with sandboxed code execution using TS, and GPT-4o \- E2B, accessed January 27, 2026, [https://e2b.dev/blog/build-ai-data-analyst-with-sandboxed-code-execution-using-typescript-and-gpt-4o](https://e2b.dev/blog/build-ai-data-analyst-with-sandboxed-code-execution-using-typescript-and-gpt-4o)  
6. Build LangChain agent with code interpreter — E2B Blog, accessed January 27, 2026, [https://e2b.dev/blog/build-langchain-agent-with-code-interpreter](https://e2b.dev/blog/build-langchain-agent-with-code-interpreter)  
7. Recursive Language Models \- arXiv, accessed January 27, 2026, [https://arxiv.org/pdf/2512.24601](https://arxiv.org/pdf/2512.24601)  
8. Paper page \- Recursive Language Models \- Hugging Face, accessed January 27, 2026, [https://huggingface.co/papers/2512.24601](https://huggingface.co/papers/2512.24601)  
9. Recursive Language Models \- RLM \- arXiv, accessed January 27, 2026, [https://arxiv.org/html/2512.24601v1](https://arxiv.org/html/2512.24601v1)  
10. Reverse engineering Claude Code | Reid Barber, accessed January 27, 2026, [https://www.reidbarber.com/blog/reverse-engineering-claude-code](https://www.reidbarber.com/blog/reverse-engineering-claude-code)  
11. rlm-claude-code-spec.md \- GitHub, accessed January 27, 2026, [https://github.com/rand/rlm-claude-code/blob/main/rlm-claude-code-spec.md](https://github.com/rand/rlm-claude-code/blob/main/rlm-claude-code-spec.md)  
12. A practical guide for using AutoGen in software applications | by Clint Goodman \- Medium, accessed January 27, 2026, [https://clintgoodman27.medium.com/a-practical-guide-for-using-autogen-in-software-applications-8799185d27ee](https://clintgoodman27.medium.com/a-practical-guide-for-using-autogen-in-software-applications-8799185d27ee)  
13. Inside AutoGen: Chapter 7— Core | Agents & Runtime | by Okan Yenigün | T3CH \- Medium, accessed January 27, 2026, [https://medium.com/h7w/inside-autogen-chapter-7-core-agents-runtime-d9af4511e1a4](https://medium.com/h7w/inside-autogen-chapter-7-core-agents-runtime-d9af4511e1a4)  
14. Agent Runtime implemented using Ray · Issue \#4106 · microsoft/autogen \- GitHub, accessed January 27, 2026, [https://github.com/microsoft/autogen/issues/4106](https://github.com/microsoft/autogen/issues/4106)  
15. Distributed Agent Runtime — AutoGen \- Microsoft Open Source, accessed January 27, 2026, [https://microsoft.github.io/autogen/stable//user-guide/core-user-guide/framework/distributed-agent-runtime.html](https://microsoft.github.io/autogen/stable//user-guide/core-user-guide/framework/distributed-agent-runtime.html)  
16. Defining the LangGraph state. In a previous article, I introduced a… | by Martin Hodges | Medium, accessed January 27, 2026, [https://medium.com/@martin.hodges/defining-the-langgraph-state-47c5ef97a95c](https://medium.com/@martin.hodges/defining-the-langgraph-state-47c5ef97a95c)  
17. LangGraph overview \- Docs by LangChain, accessed January 27, 2026, [https://docs.langchain.com/oss/python/langgraph/overview](https://docs.langchain.com/oss/python/langgraph/overview)  
18. Graph API overview \- Docs by LangChain, accessed January 27, 2026, [https://docs.langchain.com/oss/python/langgraph/graph-api](https://docs.langchain.com/oss/python/langgraph/graph-api)  
19. Serialization — Ray 2.53.0 \- Ray Docs, accessed January 27, 2026, [https://docs.ray.io/en/latest/ray-core/objects/serialization.html](https://docs.ray.io/en/latest/ray-core/objects/serialization.html)  
20. How exactly does Ray share data to workers? \- Stack Overflow, accessed January 27, 2026, [https://stackoverflow.com/questions/58082023/how-exactly-does-ray-share-data-to-workers](https://stackoverflow.com/questions/58082023/how-exactly-does-ray-share-data-to-workers)  
21. Objects — Ray 2.53.0, accessed January 27, 2026, [https://docs.ray.io/en/latest/ray-core/objects.html](https://docs.ray.io/en/latest/ray-core/objects.html)  
22. Fast Python Serialization with Ray and Apache Arrow, accessed January 27, 2026, [https://ray-project.github.io/2017/10/15/fast-python-serialization-with-ray-and-arrow.html](https://ray-project.github.io/2017/10/15/fast-python-serialization-with-ray-and-arrow.html)  
23. Actors — Ray 2.53.0 \- Ray Docs, accessed January 27, 2026, [https://docs.ray.io/en/latest/ray-core/actors.html](https://docs.ray.io/en/latest/ray-core/actors.html)  
24. Ray: Your Gateway to Scalable AI and Machine Learning Applications \- Analytics Vidhya, accessed January 27, 2026, [https://www.analyticsvidhya.com/blog/2025/03/ray/](https://www.analyticsvidhya.com/blog/2025/03/ray/)  
25. Managing Computation — Dask.distributed 2026.1.1 documentation, accessed January 27, 2026, [https://distributed.dask.org/en/latest/manage-computation.html](https://distributed.dask.org/en/latest/manage-computation.html)  
26. Related Work — Dask.distributed 2025.12.0 documentation, accessed January 27, 2026, [https://distributed.dask.org/en/stable/related-work.html](https://distributed.dask.org/en/stable/related-work.html)  
27. Security \- Wasmtime, accessed January 27, 2026, [https://docs.wasmtime.dev/security.html](https://docs.wasmtime.dev/security.html)  
28. WebAssembly/WASI Sandbox \- Emergent Mind, accessed January 27, 2026, [https://www.emergentmind.com/topics/webassembly-wasi-sandbox](https://www.emergentmind.com/topics/webassembly-wasi-sandbox)  
29. WASI and the WebAssembly Component Model: Current Status \- eunomia-bpf, accessed January 27, 2026, [https://eunomia.dev/blog/2025/02/16/wasi-and-the-webassembly-component-model-current-status/](https://eunomia.dev/blog/2025/02/16/wasi-and-the-webassembly-component-model-current-status/)  
30. Introduction to WAMR WASI threads \- GitHub Pages, accessed January 27, 2026, [https://bytecodealliance.github.io/wamr.dev/blog/introduction-to-wamr-wasi-threads/](https://bytecodealliance.github.io/wamr.dev/blog/introduction-to-wamr-wasi-threads/)  
31. Announcing wasi-threads \- Bytecode Alliance, accessed January 27, 2026, [https://bytecodealliance.org/articles/wasi-threads](https://bytecodealliance.org/articles/wasi-threads)  
32. Creating an ungodly amount of sub interpreters in a short amount of time causes memory debug assertions. · Issue \#123134 · python/cpython \- GitHub, accessed January 27, 2026, [https://github.com/python/cpython/issues/123134](https://github.com/python/cpython/issues/123134)  
33. CVE-2025-68668 Deep Dive: The n8n Pyodide Sandbox Escape & AI Infrastructure Risk, accessed January 27, 2026, [https://www.penligent.ai/hackinglabs/cve-2025-68668-deep-dive-the-n8n-pyodide-sandbox-escape-ai-infrastructure-risk/](https://www.penligent.ai/hackinglabs/cve-2025-68668-deep-dive-the-n8n-pyodide-sandbox-escape-ai-infrastructure-risk/)  
34. Code as Policies: Language Model Programs for Embodied Control, accessed January 27, 2026, [https://code-as-policies.github.io/](https://code-as-policies.github.io/)  
35. \[2209.07753\] Code as Policies: Language Model Programs for Embodied Control \- ar5iv, accessed January 27, 2026, [https://ar5iv.labs.arxiv.org/html/2209.07753](https://ar5iv.labs.arxiv.org/html/2209.07753)  
36. \[2209.07753\] Code as Policies: Language Model Programs for Embodied Control \- arXiv, accessed January 27, 2026, [https://arxiv.org/abs/2209.07753](https://arxiv.org/abs/2209.07753)  
37. ICML Poster Language Agent Tree Search Unifies Reasoning, Acting, and Planning in Language Models \- ICML 2026, accessed January 27, 2026, [https://icml.cc/virtual/2024/poster/33107](https://icml.cc/virtual/2024/poster/33107)  
38. Language Agent Tree Search \- GitHub Pages, accessed January 27, 2026, [https://langchain-ai.github.io/langgraph/tutorials/lats/lats/](https://langchain-ai.github.io/langgraph/tutorials/lats/lats/)  
39. Message-passing concurrency in Erlang \- Lecture 8 of TDA383/DIT390 (Concurrent Programming) \- Page has been moved, accessed January 27, 2026, [https://www.cse.chalmers.se/edu/year/2016/course/TDA383\_LP3/files/lectures/Lecture08-message-passing.pdf](https://www.cse.chalmers.se/edu/year/2016/course/TDA383_LP3/files/lectures/Lecture08-message-passing.pdf)  
40. Erlang (programming language) \- Wikipedia, accessed January 27, 2026, [https://en.wikipedia.org/wiki/Erlang\_(programming\_language)](https://en.wikipedia.org/wiki/Erlang_\(programming_language\))  
41. Introduction to Actors \- Akka Documentation, accessed January 27, 2026, [https://doc.akka.io/libraries/akka-core/current/typed/actors.html](https://doc.akka.io/libraries/akka-core/current/typed/actors.html)  
42. Tour of Akka Typed: Protocols and Behaviors \- Manuel Bernhardt, accessed January 27, 2026, [https://manuel.bernhardt.io/2019/07/11/tour-of-akka-typed-protocols-and-behaviors/](https://manuel.bernhardt.io/2019/07/11/tour-of-akka-typed-protocols-and-behaviors/)  
43. Agent Contracts: A Formal Framework for Resource-Bounded Autonomous AI Systems (Full), accessed January 27, 2026, [https://arxiv.org/html/2601.08815v2](https://arxiv.org/html/2601.08815v2)  
44. Agent Contracts: A Formal Framework for Resource-Bounded Autonomous AI Systems (Full), accessed January 27, 2026, [https://arxiv.org/html/2601.08815v1](https://arxiv.org/html/2601.08815v1)  
45. LbMAS Implementation: Multi-Agent LLM System \- Emergent Mind, accessed January 27, 2026, [https://www.emergentmind.com/topics/lbmas-implementation](https://www.emergentmind.com/topics/lbmas-implementation)  
46. PAT: Blackboard Architecture \- CAST, accessed January 27, 2026, [https://www.doairight.org/posts/pat-blackboard-ai/](https://www.doairight.org/posts/pat-blackboard-ai/)  
47. Announcing File Persistence in Hosted Apps… for Everyone\! \- Replit Blog, accessed January 27, 2026, [https://blog.replit.com/filesystem-persistence-for-all](https://blog.replit.com/filesystem-persistence-for-all)  
48. Inside Replit's Snapshot Engine: The Tech Making AI Agents Safe, accessed January 27, 2026, [https://blog.replit.com/inside-replits-snapshot-engine](https://blog.replit.com/inside-replits-snapshot-engine)  
49. Replit Storage: The Next Generation, accessed January 27, 2026, [https://blog.replit.com/replit-storage-the-next-generation](https://blog.replit.com/replit-storage-the-next-generation)  
50. Devin June '24 Product Update \- Cognition, accessed January 27, 2026, [https://cognition.ai/blog/june-24-product-update](https://cognition.ai/blog/june-24-product-update)

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACMAAAAYCAYAAABwZEQ3AAAEnElEQVR4AXSWTcimcxTGr/8zmgUpFqNJGTLDYkyJptjoFWUxmNIQ0ZRSFmNtZ8FCmcSCKUvEvJSvEgv5esWEMLPxNTWGQpKyYBBec/td55z743ned+6u8z/Xuc75n/+5n+d+7vedaZ2rhZZrUMFB8umKCKbKwAc9Sa5kIQCyAMR1h+miLtegggPPlDE7gyCCoJMlstYhzXvJOcRJXa84ogAXKwWTYZAAuQQcJO9XNphO2znGzsBO6+urbOFgKqJgyCIkz1XKYRq6kIBZWN1BpELol4VRsuBxslun24nBnDLjiMsQb8R2YBo/acl8Fr3GPbdJ+o7E99zWt5KOkzqGvx0roBSrvf5ULkI6iq2Hs6R2QNIhzH2209/xVwx3BRohKzc/w2ADnoddQNGR8NI+/DZsOQ6GTOGx0G9Ce9Ud4VBWADFuYPmSG/tJaldJuhfbT/+r8a9hK9jOnKHjazIbN5NTI7wScgJ7Gwv44CAimyRW9Dsgyxwgt+LgANoe7BXsIexBxFX8FPcT/I09LJrgxdcEAw7KthNugr+P/YvV8QwBaGqpt3Mhfu5+xGeKGrCF+EnMd/4Yfg2o+QPxC8yf0pnilBkH48RFmhU4idO7XkR2vOOhRnX5GXiueDoagieo9AG++9RrRQ+WPfVfBNJW34nvSpmgRWb6YVaYAwUdQAiLOAhr/ipeCko2vS7H76KSu+780BKOQM8gDz0/A4ZiyhhGVUEMtETf3yg6otLhAYcuiEC6lLvhF9d+px6psk27CEB7w/qkHm2K7jwif53/4L8R23MYIrGT+BJJm0h8gF8dGg2E40e+ly3PoASoB3TodC0EdJ/QR/kBEFLsNS2a7I5VegftT0w5DGq+ytqSRew9TLTOFiYWbO7etEHSNRS8iV/ExhCafqZtDjqQyLC4ie6qto8gBHIYVMDB3dwwrrBuH9Y3zbtfQePnGiJ0wNfBOm0c9hYZKptupsZv42X8W1gghwmqxp4lNpwg/AwroBTjk+jZXsizGGAXK3fiFWuHiu8kmENVbqHPAWp8xt3TgukwTNrOYcNHFKxiBZRi5fz6vxh+GBtRZXzdT3PYhxx2D7exOQog4aUd6H5GDlNzHZrfNTgKgIe5hegYRbxtu7/gfvsex9+JzYMNCH79v4wvpFgBZ/AzlfZAPma+T9Hvg+/D87DroLr2APx67FdMnKt4sCj2MC8QbVOns/GnY7ysdCH+qeGYnvi5a/KL7qA0iFpzNfG3SB7avyw/Q79Qsx/j0+881Em4ogND9NzDmJdFOotQqi4GJwTdZobeAPkhxawnThCCTKVyFPciDX3Dn0vtJFz9NfRHMK9haAH6Lk6QByHW/uC3svoXQM4YKx2JTw4EnVsssjH615YIq3PWNtUwVACtuVIc17YbXq//LM6myaeH9Up6dgGfnfU85pGwCAmxq2EiQCwshKgoTXw93euS/NPHJapdBsNK/cCThEIxQPAaiufjHpLzL0TlcImcOtOpUG34L+yjvZJdhmgh9GFjzuxUivU8UZr8C+EtNqd9trmtaeEkxZVlQUWBHwvFRT0+VwgY+ECm4njW/wAAAP//rk1mFQAAAAZJREFUAwASqSZKzwy5PwAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAYCAYAAAAlBadpAAACOElEQVR4AWySvUuVYRjGr/c0FBVBEURQkCnR3GDRIKdAwjVaor1/oKHWGoKGWiIaG1oboohoym/EQRxFPDqI6KCgi4Kor7/ruZ/3PS96Hu6v676v63nu89FSj1P06IkmxoSIUainuPQke+ZJzSYz93uKPWCeLDTRibobEccgYuKffCSaxOAQQ++1o4qoh3A6jNf5jBv4GnWH3jL1Apxv7H8fnIyXU67CNEU/pDGVxTWVemaM4Db1MPU5fAp/gftlp1M+iGCb7ixe2SpbvAWcwd/hXTEDcIo3KfqkYoJVD1UdRmx0PcMWsCvOTachB3yUVW2UGEoi61qmT9QWA7CYEQu1geL852VSsovE1/hzPs4b8meYFpOwEKTYBh5Aeg/pL5058iZ+D78rFR+Uz4lvu7zBngPM/kjFCPUIFw1S/2CLYS66oMapxZDcbjvg47xMSuYtvnPRZRA/HUxuofbaTrU/ytWYeEqczLtDqbIl/84uk8fLmUHnMZod8nz1Mu8A1aYvHWlL+ViCmBQMfxm3mE3i/L70MWrbVda2ftcA/4KkH3H5ALCE+6+5B2kIzQr4CV7ZR5T7gKdS8QrOWTgdxJph4G/4ilSel3QJ78P/QSIl+0Uc4LWvcBbhvwTnL4wuNxknB6bsEH1iKf+3f0rFby49Escvk7gvRUgpOzSvMK440XcMcVNT1xRYUxYwovshdpWc+7DuuHqNYd2EALSFuMY1w7NTXtPyJMQZpIQ+SEQMSJtY1wHp6BgAAP//55PlxwAAAAZJREFUAwAuWoE4nT4JkQAAAABJRU5ErkJggg==>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAXCAYAAADUUxW8AAACFUlEQVR4AWyQP0tcQRTFz0iaVKbJnyqVhjWpQro0IakiKGKnn0AEO7ERxW8gCDYWYmFlpdiIWguWdrsqWNmL2im4/s7cebOrOJw7c865986d9wbklbyVeJNjglKRD0uafUixS+qqx9UsTNAoF1jS7CP31FwlkULWq4MXn+ZIxB45dhBO7KUat4F9mkmAxuTsIM95ywXPu0ATqQ3fcAM6gxrRnLk/NYjUoqiFOMEcpmgFPgKf4aygxs0cSaO4E1IapKhA92KRvZUdOBd9g0/yil9IN/vQP4r2SOySMLLpjQYAS/pCzRlsi/hEiGeT62qB/RrjD0PecfaDFLKr3+zviW3iwCbN3Be4khJan50QC9uvaGSehn3FAA7VydZtnm1zKHlXSu5yZCl9LbyjKHBzYdKhcAeS/qpZkYpd+o/NT0ynngR3MwdpwA/T0VNX80z4ziuSi/CB5qj6SSwSN0SGvzETGoDGEGtU73OOE8aqlGYlTeGvcylUgnsyPcCCxCPukqQh4pgwlvF/QHYIQCWgxc0wrAq7IXyR2YO40VBeFADT/mej80UdyCUxzTffUbfJ5DZ8A+8FaCade+xn3mIfRn0gBomPxAiTZ/ChtdjPRocLIVE5sqLfpwAJSnMtIgF3QoxSXeFXWQjPjtKi8xGl7K9SIdlJgd5krNzYG1gd/OBu4OehA0yGRA4CogIC4P0pHIAT0DMAAAD//3g1AIkAAAAGSURBVAMAwaKAOLHuS9YAAAAASUVORK5CYII=>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAYCAYAAAAlBadpAAACNElEQVR4AWySu0teURDE55g3pEiVBIuQIpA6hFQhpAkJeRgC+Q+SIiGEEBBBGwWxshAbQdBOEGsfoIWCICI+ai3tLETUQkREr785e7/LVb/L7NnZ2Z3z8LNF5ZfK7HSdowD36hFmGkVWIeTgEFDxiiCWCDON6zYmEAGEAdY6rIf5iupGKd3F9hb+RUmtNR1JwpxEQwxJJpL5c+hkKjRN1+ZXyAvMzJEfEZ6xGQlYwMasuuCLdEeQ38F7pdRD/ULSPSmtSLpP2OzUiDTAUDfVV2KKoCzXpGOYN37Krdp9CtdGMpO+cfJ/Gn2SVgUxdPlbZ4YLqc1LmKUH+IckHUgaVLPP09KZlMyeiQ8ztkI/UFqpx4kjFFKgzlGecHILb2ET+c3YlD7RAGmWhgFviteKt2yKj5N1m93ewEGx5l6CZXjfTFACbcxayX9MmxOGmyjnxC5x6eTwsxZ6yMqvkA6ZH00M2nxC3ibMb9npRj4hCK2MHso7sA5m9sh+M1KhJRfES3alBzM4iq7ZZ5bflMPkkcYMpyEldTK0r/hPugFX46P7HT6BoZ/8N98IYmDOozsMfUB4TCzD/5HbiXniF/GR63QxmX8i6gzMjEJprJF87T9kbqEt8k/iPdF4FhSEpXozGyOqOIVswMaIGWKbTUnNESc3nUAE5SHizYoPMUh5clnkVPWwgShjpWQkVitxctQ06qANohVrvWsFMxNX1FBog6oFDz1W65hJVR2EuRCjhAdCD+71AgAA///To8PSAAAABklEQVQDAMkjiTfV0LRWAAAAAElFTkSuQmCC>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAYCAYAAADKx8xXAAACJ0lEQVR4AWSTvWpVURCFv33QQgUrEVFs/EGwUkgjKLliZWHlK/giFr6D2IhPIIh2FhEFkYu+gH+gIgjBJoEUSTj5Zmafww05zJ5ZM7PW7DknuQP9aT1GmLFAixIINOhgFo5MT2MsBlg8hKXYzfrQB1jSUhDswlNqFjSDMosaQ061lBbjrWo51RFZDlctK2UMSaLdcuRS9tJBS3ti6rQexxb1j/I3oN0cJOECjxQcAx57HnoeeDY9a4ztifG+Q6P+VP66eGuAdtzkDnDP85rGL+M/zw3PtqQ30DZ7/YX4D/BT4XhX8NLGf9eQl/6atXOeD9Z3LaaZB/+vcV/ABanPXClMnvfDgno2iFRCpZwyvvIQwudj43uOFATPRmxhwA9BtvRhW7p45xRWI6emLNBCF6TPrhAm34omSIsbE+RKha5DO+uI98Be1MVCvRsJ0mbhyjDXlATvmIsCrVZLXV9VnFSjtuiC+cO06doUy5CQN1aubwz6dXnxfl/Eecm84Tx9RGHOozPWJJ0x+eTZExu0EOQUsbeFVzieh/bV/Jvit962A9yW91vsn4lLYltW02qKQvxPGK9KumL9tKST0E5420XgsueH2Lmi8BJiSgiZcyz1BsE2T/OSSPOlChAfQ3Za6AUqNUFqwlWaMjkxBfJnFc04lgx6TdBtRVAyvcLstvSzW02PymqXesd+wyToaQ4qHN4RE8FOCQW4QLSZHknalBnt9g9jwgEAAAD//wkzwlUAAAAGSURBVAMAXbytNpdS7FgAAAAASUVORK5CYII=>