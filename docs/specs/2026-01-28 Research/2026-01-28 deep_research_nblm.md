# Composable Code-Executing LLM Agents: Architectures for Recursive Execution, Distributed State, and Formal Coordination  
The rapid advancement of large language models (LLMs) has transitioned the field from passive text generation to active agentic computation. As these systems evolve, the necessity for modularity and composability has become paramount. Current industry standards often rely on string-based communication between agents, which introduces significant bottlenecks in data fidelity and computational overhead. The paradigm shift toward REPL-first architectures, where agents execute code and return high-level Python objects rather than unstructured strings, represents a critical leap toward creating "autonomous functions" powered by intelligence. This report evaluates the current landscape of code-executing agents, the underlying coordination primitives, and the distributed systems required to support object-based agent composition.  
## Prior Art: REPL-First Agent Architectures  
The architectural transition from "tool calling"—where an LLM outputs a structured schema for an external system to execute—to "REPL-first execution"—where the LLM operates within a continuous, stateful execution environment—marks a fundamental shift in agentic reasoning. In a REPL-first model, the execution environment serves as the primary cognitive scratchpad, allowing the model to define variables, import libraries, and maintain state across multiple conversational turns.  
### Comparative Analysis of Existing REPL-First Systems

| System | Execution Environment | State Persistence | Error Handling Strategy | Core Capability Focus |
| ----- | ----- | ----- | ----- | ----- |
| Open Interpreter | Local/Remote Shell & Python | Persistent OS process | Interactive loop; terminal-native debugging | Local file manipulation & automation |
| E2B Code Interpreter | Sandboxed Micro-VMs | Session-scoped kernel persistence | Programmatic traceback feedback | Secure, isolated data science & analysis |
| Claude Code | Terminal CLI | Filesystem & `CLAUDE.md` context | Agentic planning; iterative self-repair \[1\] | Software engineering & codebase refactoring |
| GPT Code Interpreter | Ephemeral Container | Session-based (variable state) | Automatic retry on runtime errors | General-purpose scripting & visualization |
| MemGPT | Virtual OS Abstraction | Tiered memory via tool calls | Retrieval-augmented state recovery | Long-term memory & context management |
| Recursive LM (RLM) | Python REPL | Variable-based context environment \[2, 3\] | Recursive sub-querying for clarification \[4\] | Massive context (10M+) processing \[5\] |

Open Interpreter provides a direct interface to the user’s operating system, enabling a seamless transition between bash commands and Python scripts. However, its primary failure mode is the lack of formal isolation, making it susceptible to destructive commands unless strictly monitored by a human-in-the-loop. E2B addresses this through micro-VM sandboxing, which offers a robust state persistence model where the Python kernel remains alive across API calls, allowing agents to maintain complex objects like DataFrames or machine learning models in memory.\[6\]  
Claude Code represents a hybrid approach where the "REPL" is effectively the local terminal itself, but the model is governed by persistent configuration files (`CLAUDE.md`). This allows for a deeper integration with version control systems like Git, where the agent can manage merge conflicts and create pull requests as part of its execution cycle.\[1, 7\] MemGPT, while not a pure REPL, introduces the concept of "memory management via code," where the agent explicitly manages its context window using `read_memory` and `write_memory` operations, analogous to page-table management in operating systems.  

The most advanced iteration of the REPL-first concept is found in Recursive Language Models (RLMs). By treating the entire context window as an environment variable (e.g., `context = "..."`), RLMs allow the agent to use Python to slice, search, and analyze data that would otherwise exceed the physical context limits of the underlying model.\[4\] This architecture mitigates "context rot," a phenomenon where performance degrades as input length increases.\[4, 5\]  
### Design Implications for REPL-First Agents  
The transition to REPL-first interfaces necessitates a move away from ephemeral execution. To support composability, the environment must support:  
1\. **Handle Persistence**: Variables defined by one agent must be referenceable by subagents without serializing the entire state to a string.  
2\. **Error Transparency**: Tracebacks must be provided to the model in full, as the LLM's ability to "self-correct" is predicated on the granularity of the error message.  
3\. **Environment Parity**: Subagents should ideally inherit the same virtual environment (dependencies, environment variables) as the parent to ensure object compatibility.\[2\]  

## Multi-Agent Orchestration and Data Handoffs  
Current multi-agent systems are primarily "conversation-centric," meaning agents communicate by passing text messages. While effective for brainstorming, this is highly inefficient for computational tasks where the output of one agent is a complex data structure required by another.  

### Analysis of Orchestration Frameworks

| Framework | Communication Paradigm | Data Handoff Format | Coordination Logic | Failure Mode |
| ----- | ----- | ----- | ----- | ----- |
| AutoGen | Asynchronous Conversation | Strings (JSON possible) | Event-driven; peer-to-peer \[8, 9\] | Message loops; state inconsistency |
| CrewAI | Role-based / Sequential | Strings (Sequential context) | Hierarchical "Crew" container \[8, 10\] | Lack of advanced load balancing |
| LangGraph | Graph-based State Machine | Shared State (JSON-compatible) | Directed Acyclic Graphs (DAGs) \[8, 11\] | Complexity in non-linear flows |
| OpenAI Swarm | Stateless Functional Handoff | Message list | Direct agent switching \[8\] | Loss of intermediate context |
| MetaGPT | SOP-based Workflow | Standardized documents | Organizational roles \[11\] | Rigid structure; lack of adaptivity |

In LangGraph, agents communicate indirectly via a shared graph state. While this allows for more structured workflows than AutoGen’s free-form chat, the state is typically serialized to JSON for checkpointing, which strips away the "liveness" of Python objects.\[11, 12\] CrewAI facilitates role-based collaboration, where a "Researcher" agent passes its findings to a "Writer" agent, but the handoff is almost always a summarized string injected into the next agent's prompt.\[8, 9\]  
The fundamental gap identified in these systems is the absence of an "Object Store" mechanism. In the user’s proposed framework, if Agent A creates a `SQLAlchemy` connection object, Agent B should be able to receive that object directly to perform queries. Existing systems like AutoGen would require Agent A to close the connection, serialize the query results to a string, and for Agent B to parse that string and potentially open its own connection—a process prone to data loss and latency.  
Discovery and Parallelism  
Agent discovery—how an agent knows what subagents are available—is typically handled via hard-coded registries or LLM-based classification. In Thespian-based systems, global naming allows actors to resolve addresses dynamically.\[13\] Parallel coordination is often implemented through work queues or asynchronous message buses (like in AutoGen), but these systems struggle with "race conditions" where two agents might attempt to modify the same shared state simultaneously.\[9\]  
Distributed Computing Patterns for Object Passing  
To enable agents to return Python objects, the system must leverage distributed computing frameworks that handle object serialization, memory locality, and remote execution.  
Serialization Semantics and Object Handling

| Framework | Serialization Method | Data Mutation | Large Object Handling | Failure Recovery |
| ----- | ----- | ----- | ----- | ----- |
| Ray | Pickle / Cloudpickle | Immutable (in store) | Plasma shared-memory store \[14\] | Task lineage; actor restart \[15\] |
| Dask | Cloudpickle | Immutable collections | Distributed memory partitioning \[16\] | Task graph re-execution \[16\] |
| Celery | JSON / Pickle / MessagePack | Shared state via DB/Redis | External storage required | Task retries; persistent broker |
| Apache Spark | Java Serialization / Kryo | Immutable RDDs / DataFrames | Spill-to-disk; sharding | Lineage-based re-computation |

Ray's architecture is particularly relevant due to its support for both stateless "Tasks" and stateful "Actors".\[15\] Ray uses the Plasma object store to enable zero-copy reads, which is essential when agents are passing large datasets (e.g., a 2GB NumPy array) to subagents. Objects in Ray are immutable once placed in the store, which simplifies the coordination of parallel agents by preventing shared-state corruption.\[15\]  
A significant risk in this domain is the use of `pickle` for serialization. `Pickle` is inherently unsafe as it can execute arbitrary code during deserialization.\[17, 18\] Research into "Fickling" and other static analyzers reveals that even "safe" pickling tools often fail to block dangerous modules like `pydoc` or `cProfile`, which can be exploited for Remote Code Execution (RCE).\[18\] For a composable agent framework, a more secure serialization protocol like `JsonPlusSerializer` (used in LangGraph) or Apache Arrow (for tabular data) should be prioritized for cross-agent communication.\[12, 14\]  
Memory Locality and Object References  
In a distributed agent framework, passing a "Future" or a "Reference" is more efficient than passing the object itself. ProxyStore, a library discussed in academic literature, extends the pass-by-reference model to distributed applications, allowing data flow to be decoupled from control flow.\[19\] This enables an agent to receive a "Proxy" to a large object and only fetch the data if and when it is actually needed for computation.  
Capability and Permission Models for Code Execution  
The ability to execute code and spawn subagents creates a nested security risk. A robust framework must enforce fine-grained restrictions that prevent an agent from escalating privileges or accessing sensitive data while still allowing it to perform its designated task.  
Granular Security Mechanisms

| Model | Restriction Mechanism | Granularity | Performance Cost |
| ----- | ----- | ----- | ----- |
| WebAssembly (WASI) | Capability-based security | Very High (individual API access) | Low to Moderate |
| Docker / Containers | Namespaces, cgroups, seccomp | High (OS resource level) \[6\] | Moderate |
| RestrictedPython | AST-level sanitization | Medium (blocks dangerous keywords) | Very Low |
| E2B Sandboxes | Micro-VM / Firecracker | High (full isolation) \[6\] | Moderate to High |
| Pyodide | Browser-level sandbox | High (JS-isolated environment) | Moderate |

Fine-grained restrictions are often implemented at the protocol level. For example, AgentPool provides "Tool Confirmation Modes" where users can toggle between auto-approval and manual confirmation for destructive terminal commands or file writes.\[6\] This allows a system to grant a subagent "permission to spawn" another subagent but "deny filesystem access," effectively creating a "computation-only" node in the hierarchy.  
A key design implication is that permissions should be inherited but bounded. Using "Agent Contracts," parents can delegate a portion of their budget (tokens, time, or compute) to children, but the child cannot exceed the parent's total allocation.\[11\] This "conservation law" for resources prevents runaway execution in recursive systems.  
Academic Literature on Recursive and Hierarchical Agents  
Academic research into LLM agents has moved from simple prompting to complex reasoning scaffolds. The concept of agents-as-functions is deeply rooted in the literature on "Program-aided Language Models" (PAL) and "Code as Policies."  
Key Academic Research Themes  
• **Recursive Language Models (RLMs)**: Zhang and Khattab (2025) propose a paradigm where the model treats the prompt as an environment it can recursively query.\[2, 5\] This allows the agent to handle contexts of near-infinite length by partitioning the data and spawning sub-calls to process specific segments.\[3\]  
• **Language Agent Tree Search (LATS)**: This approach integrates planning, acting, and reasoning by using Monte Carlo Tree Search (MCTS) to navigate potential agent trajectories. It allows agents to backtrack if a code execution path fails.  
• **ReAct (Reason \+ Act)**: Yao et al. established the foundational loop of interleaving reasoning traces with environment interactions, which is the precursor to REPL-first execution models.\[20\]  
• **Agent Contracts**: Recent work on formal resource governance introduces "contracts" that bound how much an agent can consume, providing the first formal framework for hierarchical coordination that includes cost and time deadlines.\[11\]  
The RLM paper is particularly significant for the user's framework. It demonstrates that an agent (root LM) can use a REPL to analyze a long context and then launch recursive calls over specific variables stored in that environment.\[3, 4\] This provides an empirical basis for the "agents-as-functions" concept, showing that RLM(GPT-5-mini) can outperform base GPT-5 on complex long-context tasks while being more token-efficient.\[3\]  
Actor Model and Supervision trees  
The Actor Model offers a mature paradigm for managing concurrent, stateful agents. By treating each agent as an independent actor that communicates via message passing, the system gains inherent fault tolerance and scalability.  
Actor Model Implementation in Python

| System | Concurrency Model | State Isolation | Supervision Mechanism |
| ----- | ----- | ----- | ----- |
| Thespian | Process/Thread/TCP based | Complete isolation | Parent receives `ChildActorExited` \[21\] |
| Pykka | Thread-based | Shared address space | Registry-based monitoring \[22, 23\] |
| Akka (JVM) | Event-driven (lightweight) | Actor-local state | Supervision trees (Restart, Stop, Resume) \[24\] |
| Orleans (.NET) | Virtual Actors | Automatic activation | Perpetual availability; silo-based recovery \[24\] |

In an actor-based agent system, the "Orchestrator Agent" acts as a supervisor.\[13\] If an action agent fails due to an LLM hallucination or a runtime error, the supervisor can catch the failure through a `ChildActorExited` message and decide to retry the task with a different prompt or model.\[13, 21\] Thespian's "Location Transparency" is a critical feature, as it allows the agent system to be distributed across multiple servers without changing the logic of how subagents are spawned or managed.\[13, 24\]  
Message passing in these systems is often "typed." In the `llm-actor-agent-framework`, type-safe message classes like `QueryMessage` and `IntentAgentMessage` ensure that agents have a clear contract for communication, reducing the risk of parsing errors that commonly plague string-based frameworks.\[13\]  
Coordination Primitives and Patterns  
Effective multi-agent systems rely on coordination patterns that allow autonomous entities to share information and resolve conflicts without a central bottleneck.  
Comparative Coordination Patterns

| Pattern | Mechanism | Implementation Example | Mapping to LLM Agents |
| ----- | ----- | ----- | ----- |
| Blackboard | Shared knowledge base | LbMAS, Data Discovery \[25, 26\] | Agents post inferences; others refine them \[27\] |
| Contract Net | Bidding for tasks | FIPA-Standard protocols | Agents bid on tasks based on capability/load \[28\] |
| Work Queues | Producer/Consumer | Celery, RabbitMQ | Simple task distribution; no peer negotiation |
| Stigmergy | Environment marking | Ant-colony simulations | Agents leave "hints" in the codebase/REPL state |
| Market-based | Resource pricing | Agent Contracts \[11\] | Agents trade tokens/compute for tasks |

The **Blackboard Architecture** is particularly effective for LLM agents. In the Lattice Boltzmann Multi-Agent System (LbMAS), a shared blackboard stores all agent-generated messages and intermediate inferences.\[25\] A control unit selects which agent should act next based on the blackboard's content, allowing for a dynamic, non-linear reasoning path that is far more flexible than a static graph.\[25, 29\] This approach reduces token usage because agents do not need to repeat context—they simply refer to the shared "public memory".\[25\]  
The **Contract Net Protocol (CNP)** addresses the "discovery" problem. A manager agent announces a task, and subagents "volunteer" based on their expertise.\[26\] This is highly scalable for "data lake" scenarios where thousands of files might be partitioned among specialized retrieval agents.\[26\]  
Industry Practice in Multi-Step Workflows  
Production systems like Claude Code and Devin have begun to implement these patterns, although their internal architectures remain largely proprietary.  
Industry Architectural Trends  
• **Claude Code (Anthropic)**: Focuses on "unopinionated" access to the terminal, using the filesystem as a persistent context layer. It emphasizes "Tool Use Proficiency" and agentic planning, allowing the model to edit files and fix bugs across a codebase.\[1, 7\]  
• **Devin (Cognition)**: Utilizes a persistent browser and shell environment, effectively acting as a long-running REPL. It features a "planner" that breaks down high-level goals into subtasks, which is functionally equivalent to a root agent spawning subagents.  
• **Replit Agent**: Integrated directly into the IDE's cloud-based REPL, it leverages Replit's infrastructure for deployment and hosting, providing a seamless loop between code generation and execution.  
• **Cursor**: Uses a "shadow" REPL to index and search codebases, employing RAG-based strategies to provide context to the LLM during code generation.  
These systems increasingly adopt the **"Human-in-the-loop" (HITL)** pattern, not just for safety, but as an "expert" agent on a blackboard.\[27\] The human can play the role of a "conservative architect," triaging the enthusiastic (but error-prone) suggestions of the LLM agents.\[27\]  
Synthesis: Addressing the Problem Space Challenges  
The design of a composable, code-executing agent framework must address specific gaps identified in existing systems.  
Answers to Specific Research Questions  
1\. **Passing Python Objects vs. Strings**: There is currently no mainstream LLM framework that natively passes live Python objects between agents as its primary communication mode. Systems like LangGraph and AutoGen are constrained by JSON/string serialization. However, distributed frameworks like **Ray** and **Dask** have the infrastructure (object stores, futures) to support this if integrated with an LLM agent scaffold.  
2\. **Restricting Capabilities**: The state of the art involves **capability-based sandboxing** using micro-VMs (E2B) or WASI. Fine-grained control is achieved through protocol-level "Permission Gates" that can allow spawning but restrict filesystem/network access.\[6\]  
3\. **Actor-Model Supervision**: Yes, implementations such as the **`llm-actor-agent-framework`** and **LbMAS** have successfully combined actor-model principles (Thespian) and blackboard architectures with LLM agents to provide fault isolation and dynamic orchestration.\[13, 25\]  
4\. **Coordination Patterns**: For parallel agents, the **Blackboard architecture** and **Contract Net Protocol** are the most successful. Blackboard systems excel at collaborative reasoning, while CNP is superior for decentralized task allocation in large-scale data environments.\[25, 26, 28\]  
5\. **Benchmarks**: **MultiAgentBench** is the current state-of-the-art for evaluating collaboration and coordination. Other relevant benchmarks include **Gaia2** (for A2A coordination) and **AgentBench** (for tool use).\[20, 30, 31\]  
Design Implications and Recommendations  
The proposed framework should adopt a **Distributed Actor-REPL** architecture.  
• **Adopt Ray/Plasma for the Object Store**: To avoid the "string bottleneck," the framework should utilize an in-memory object store. Agents return "Object References" (pointers) that subagents can use to perform computation without data copying.  
• **Use Supervision Trees for Fault Tolerance**: Each agent should be a supervised actor. If a subagent returns an invalid Python object or a runtime error, the supervisor (parent agent) should receive a structured message and initiate a "reflection" turn to fix the code.  
• **Context-as-Variable Pattern**: Following the RLM research, the parent agent should store massive context in the REPL's local namespace. Subagents should be "spawned" with a reference to a slice of that variable, dramatically reducing token costs.\[3, 4\]  
• **Formal Resource Governance**: Implement "Agent Contracts" that enforce token and time budgets at the kernel level. This ensures that a recursive subagent cannot "bankrupt" the parent agent by performing infinite loops or excessive model calls.\[11\]  
• **Hybrid Serialization**: For safety, use a combination of Arrow (for data) and restricted pickling (with a strict allowlist of modules) for complex objects, ensuring that agents cannot execute malicious code through the object-passing channel.\[18\]  
Advanced Considerations in Recursive Composition  
The "agents-as-functions" metaphor implies that agents must have a stable API. Just as a Python function has a signature `def func(obj: Type) -> Type`, an LLM agent should have a **Typed Agent Interface**. This requires the use of Pydantic or similar libraries to enforce that subagents return objects that match the expected schema of the parent's REPL environment.  
Causal Relationships in Agentic Failures  
The analysis of failure modes in existing systems reveals a causal chain:  
1\. **String-only communication** leads to **Parsing Errors**.  
2\. **Parsing Errors** lead to **Execution Failure**.  
3\. **Execution Failure** (without structured feedback) leads to **Hallucination** during retry.  
4\. **Object-based passing** breaks this chain by providing the LLM with direct, programmatic access to the data, removing the "translation layer" where most errors occur.  
Furthermore, the "context rot" identified in the RLM research suggests that the physical limits of the context window are not just a memory problem, but a reasoning problem. When an LLM "sees" too many tokens, its attention mechanism becomes diluted. By moving the context to a REPL variable and using recursive calls, the framework maintains **Attention Sparsity**, ensuring the model only processes the most relevant information for each sub-step.\[5\]  
Future Outlook: Toward an Agentic Operating System  
The synthesis of REPL-first execution, actor-model supervision, and distributed object stores points toward the creation of an "Agentic OS." In this system, the LLM functions as the scheduler/kernel, the REPL serves as the RAM, and the subagents are the processes. The transition to passing Python objects is the final step in moving from "Chatbots" to "Computational Intelligence."  
The integration of **Formal Resource Governance** \[11\] will be the defining feature of production-grade systems, allowing organizations to deploy recursive agents with the same confidence they have in traditional software. As benchmarks like MultiAgentBench mature, they will provide the necessary rigor to validate that these complex, emergent systems are not just "vibing" but are performing reliable, coordinated work.\[30, 32\]  
The proposed framework stands at the intersection of these trends, leveraging the modularity of function-like agents with the robustness of distributed systems. By adopting the RLM-style context management and Ray-style object passing, the framework can overcome the fundamental limitations of current "conversation-first" agentic scaffolds.  
\--------------------------------------------------------------------------------  
1\. From IDE Helpers to CLI Agents: How Agentic CLIs Are Accelerating Real-World Dev Workflows \- by Lawrence Teixeira, [https://lawrence.eti.br/2025/11/09/from-ide-helpers-to-cli-agents-how-agentic-clis-are-accelerating-real-world-dev-workflows/](https://lawrence.eti.br/2025/11/09/from-ide-helpers-to-cli-agents-how-agentic-clis-are-accelerating-real-world-dev-workflows/)  
2\. alexzhang13/rlm: General plug-and-play inference library for Recursive Language Models (RLMs), supporting various sandboxes. \- GitHub, [https://github.com/alexzhang13/rlm](https://github.com/alexzhang13/rlm)  
3\. Recursive Language Models | Alex L. Zhang, [https://alexzhang13.github.io/blog/2025/rlm/](https://alexzhang13.github.io/blog/2025/rlm/)  
4\. ysz/recursive-llm: Recursive Language Models for unbounded context processing. Process 100k+ tokens with any LLM by storing context as variables instead of prompts. \- GitHub, [https://github.com/ysz/recursive-llm](https://github.com/ysz/recursive-llm)  
5\. Recursive Language Models \- RLM \- arXiv, [https://arxiv.org/html/2512.24601v1](https://arxiv.org/html/2512.24601v1)  
6\. ACP Integration \- AgentPool \- GitHub Pages, [https://phil65.github.io/agentpool/advanced/acp-integration/](https://phil65.github.io/agentpool/advanced/acp-integration/)  
7\. AI / ML Toolkit \- GitHub Gist, [https://gist.github.com/0xdevalias/09a5c27702cb94f81c9fb4b7434df966](https://gist.github.com/0xdevalias/09a5c27702cb94f81c9fb4b7434df966)  
8\. Technical Comparison of AutoGen, CrewAI, LangGraph, and OpenAI Swarm | by Omar Santos | Artificial Intelligence in Plain English, [https://ai.plainenglish.io/technical-comparison-of-autogen-crewai-langgraph-and-openai-swarm-1e4e9571d725](https://ai.plainenglish.io/technical-comparison-of-autogen-crewai-langgraph-and-openai-swarm-1e4e9571d725)  
9\. Comparing Open-Source AI Agent Frameworks \- Langfuse Blog, [https://langfuse.com/blog/2025-03-19-ai-agent-comparison](https://langfuse.com/blog/2025-03-19-ai-agent-comparison)  
10\. Agentic AI Frameworks \- DevOps1, [https://devops1.com.au/blog/ai-agentic-frameworks](https://devops1.com.au/blog/ai-agentic-frameworks)  
11\. Agent Contracts: A Formal Framework for Resource-Bounded Autonomous AI Systems (Full), [https://arxiv.org/html/2601.08815v1](https://arxiv.org/html/2601.08815v1)  
12\. Checkpointing | LangChain Reference, [https://reference.langchain.com/python/langgraph/checkpoints/](https://reference.langchain.com/python/langgraph/checkpoints/)  
13\. Building a Multi-Agent AI System with the Actor Model: A Deep Dive ..., [https://medium.com/@kartikeyasharma/building-a-multi-agent-ai-system-with-the-actor-model-a-deep-dive-into-scalable-concurrent-ai-2e838c9815d9](https://medium.com/@kartikeyasharma/building-a-multi-agent-ai-system-with-the-actor-model-a-deep-dive-into-scalable-concurrent-ai-2e838c9815d9)  
14\. Ray Data: Scalable Data Processing for AI Workloads — Ray 2.53.0 \- Ray Docs, [https://docs.ray.io/en/latest/data/data.html](https://docs.ray.io/en/latest/data/data.html)  
15\. Ray: A Distributed Framework for Emerging AI Applications \- Duke Computer Science, [https://courses.cs.duke.edu/fall25/compsci512/internal/readings/ray.pdf](https://courses.cs.duke.edu/fall25/compsci512/internal/readings/ray.pdf)  
16\. Using Dask on Ray — Ray 2.53.0 \- Ray Docs, [https://docs.ray.io/en/latest/ray-more-libs/dask-on-ray.html](https://docs.ray.io/en/latest/ray-more-libs/dask-on-ray.html)  
17\. How to Read Common File Formats in Python \- CSV, Excel, JSON, and more\! \- Analytics Vidhya, [https://www.analyticsvidhya.com/blog/2020/04/how-to-read-common-file-formats-python/](https://www.analyticsvidhya.com/blog/2020/04/how-to-read-common-file-formats-python/)  
18\. Deserialization of Untrusted Data \- CVEs \- page 1 \- Feedly, [https://feedly.com/cve/cwe/502](https://feedly.com/cve/cwe/502)  
19\. Programming the Continuum: Towards Better Techniques for Developing Distributed Science Applications \- Knowledge UChicago, [https://knowledge.uchicago.edu/record/14920/files/pauloski-dissertation.pdf](https://knowledge.uchicago.edu/record/14920/files/pauloski-dissertation.pdf)  
20\. Gaia2: Benchmarking LLM Agents on Dynamic and Asynchronous Environments, [https://openreview.net/forum?id=9gw03JpKK4](https://openreview.net/forum?id=9gw03JpKK4)  
21\. supervisor strategy with actors using Thespian \- Google Groups, [https://groups.google.com/g/thespianpy/c/ThfsaoDt-3M](https://groups.google.com/g/thespianpy/c/ThfsaoDt-3M)  
22\. The actor model \- Pykka \- Read the Docs, [https://pykka.readthedocs.io/stable/getting-started/model/](https://pykka.readthedocs.io/stable/getting-started/model/)  
23\. Pykka: Introduction, [https://pykka.readthedocs.io/stable/](https://pykka.readthedocs.io/stable/)  
24\. What is Actor Model? \- Nikhil Akki's blog, [https://nikhilakki.in/what-is-actor-model](https://nikhilakki.in/what-is-actor-model)  
25\. LbMAS Implementation: Multi-Agent LLM System \- Emergent Mind, [https://www.emergentmind.com/topics/lbmas-implementation](https://www.emergentmind.com/topics/lbmas-implementation)  
26\. LLM-based Multi-Agent Blackboard System for Information Discovery in Data Science \- arXiv, [https://arxiv.org/html/2510.01285v1](https://arxiv.org/html/2510.01285v1)  
27\. You are the Blackboard \- AI Agent Assisted Bug Hunting by Kat Traxler \- Vectra AI, [https://www.vectra.ai/blog/ai-agent-assisted-bug-hunting](https://www.vectra.ai/blog/ai-agent-assisted-bug-hunting)  
28\. How Multi-Agent Systems Are Solving the Most Complex Problems \- Kodexo Labs, [https://kodexolabs.com/multi-agent-systems-solving-complex-problems/](https://kodexolabs.com/multi-agent-systems-solving-complex-problems/)  
29\. Exploring Advanced LLM Multi-Agent Systems Based on Blackboard Architecture \- arXiv, [https://arxiv.org/abs/2507.01701](https://arxiv.org/abs/2507.01701)  
30\. MultiAgentBench: LLM Multi-Agent Benchmark \- Emergent Mind, [https://www.emergentmind.com/topics/multiagentbench](https://www.emergentmind.com/topics/multiagentbench)  
31\. Benchmarking Multi-Agent AI: Insights & Practical Use | Galileo, [https://galileo.ai/blog/benchmarks-multi-agent-ai](https://galileo.ai/blog/benchmarks-multi-agent-ai)  
32\. From Vibe Coding to AI Agents \- Shane Drumm, [https://shanedrumm.com/vibe-coding-ai-agents/](https://shanedrumm.com/vibe-coding-ai-agents/)
