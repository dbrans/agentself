# **Architectural Paradigms for Self-Modifying Multi-Agent Systems: Image-Based Persistence and Artifact Derivation**

## **Executive Summary**

The contemporary software development lifecycle remains tethered to a file-centric paradigm where static source code serves as the definitive source of truth, and runtime behavior is a transient projection of these files. While this model has served deterministic application engineering well, it presents a fundamental structural impediment to the advancement of **Self-Modifying Multi-Agent Systems (MAS)**. Autonomous agents designed to evolve, rewrite their own logic, and spawn sub-agents require a runtime environment that functions as the primary reality—a system where the "living" object graph is the canonical state, and external files are merely derivative archival artifacts.

This research report presents a comprehensive architectural framework for such a system: the **Hyper-Persistent Containerized Agent Architecture (HPCAA)**. By synthesizing historical precedents from Smalltalk and Lisp with modern advancements in WebAssembly (Wasm), Object Capabilities (OCaps), and Orthogonal Persistence, the HPCAA establishes a runtime where agents exist as persistent, isolated memory heaps (Vats). In this model, agents can recursively improve their own code and manage sub-agent hierarchies without the friction of filesystem I/O or process restarts. Crucially, the architecture defines a "Projector" mechanism that reverse-compiles this living state into human-readable, version-control-compatible artifacts, ensuring audibility without compromising the primacy of the runtime image.

The following analysis exhaustively details the theoretical foundations, security mechanisms, persistence strategies, and implementation blueprints required to realize this paradigm shift.

## ---

**1\. Introduction: The Divergence of State and Code**

### **1.1 The Limitations of the File-First Paradigm**

In the prevailing architecture of modern software, an application’s identity is split between two distinct states: the **Source** (text files on a disk) and the **Process** (binary instructions and data in volatile memory). This duality creates a synchronization gap that is particularly deleterious for Artificial Intelligence agents designed for self-improvement.

When a conventional agent wishes to modify its behavior, it must engage in a cumbersome, high-latency cycle:

1. **Serialize Intent:** The agent must translate its new logic into a string representation of source code.  
2. **I/O Overhead:** This string must be written to a file, traversing the OS kernel boundary.  
3. **Termination:** The running process often needs to be restarted to load the new code, destroying the agent's current execution context (stack, registers, short-term memory).  
4. **Rehydration:** The agent must reload its state from a database to resume operation.

This "stop-the-world" modification loop breaks the continuity of the agent's existence. It forces a rigid separation between "learning" (updating weights or data) and "coding" (updating logic). For an AGI-adjacent system, where code generation is a form of learning, this distinction is artificial and hindering. The agent should be able to manipulate its own methods as fluently as it manipulates data variables.3

### **1.2 The Image-Based Alternative**

The alternative is **Image-Based Persistence**. In this model, the "program" is not a set of files but a snapshot of the computer's memory at a specific instant. "Saving" the program means dumping the heap to disk. "Loading" means mapping that dump back into memory. The system wakes up exactly as it was left—execution pointers, open network connections, and closure scopes intact.

For a multi-agent system, this implies that an agent is not a script running on a server; it is a **persistent object graph**. Modifying itself is as simple as changing a pointer in its method dictionary. Spawning a sub-agent is as simple as cloning a subgraph. The filesystem becomes a secondary concern, used only for interacting with legacy tools (like Git) or humans.

### **1.3 Scope of Analysis**

This report will analyze the architectural requirements for shifting to an image-based MAS. It covers:

* **Historical Prior Art:** Lessons from Smalltalk, Lisp, and early OS designs.  
* **Modern Enabling Technologies:** WebAssembly for isolation, Pyodide for language support, and Agoric SwingSet for persistence.  
* **Architectural Design:** A detailed specification of the HPCAA, including the Kernel, Vats, and the Artifact Projector.  
* **Sub-Agent Supervision:** Mechanisms for managing hierarchies of self-modifying agents safely.

## ---

**2\. Historical Prior Art and Foundational Concepts**

To design a robust modern image-based system, we must examine the mechanisms and lessons from foundational environments that treated memory as the primary storage medium. These systems solved many of the problems we face today, though often without the security boundaries required for modern untrusted code execution.

### **2.1 Smalltalk: The Canonical Image-Based System**

Smalltalk-80 and its modern derivatives like Pharo and Squeak represent the gold standard for image-based computing. In Smalltalk, the "Operating System" concept is subsumed by the language runtime.

#### **2.1.1 The Image and Changes Model**

The Smalltalk persistence model relies on two files:

* **The Image (.image):** A bit-for-bit snapshot of the object memory (heap). It contains all classes, compiled methods, live objects, and the state of the IDE itself. Launching Pharo loads this image into RAM, resuming execution exactly where it left off.4  
* **The Changes File (.changes):** To recover from crashes, Smalltalk writes every source code modification (do-it, method compilation) to a .changes file. This acts as a transactional write-ahead log. If the image corrupts, the changes file can be replayed to restore the state.5

#### **2.1.2 Code as First-Class Objects**

Smalltalk treats code as data in a profound way. A "method" is not text; it is an instance of CompiledMethod residing in the heap. The "Compiler" is simply a method that accepts a String and returns a CompiledMethod.

* **Self-Modification:** To modify itself, a Smalltalk object invokes the compiler on a string and inserts the resulting method object into its class's method dictionary. This operation is atomic and immediate. No file I/O occurs. This is the ideal user experience for a self-modifying agent.6

#### **2.1.3 The "Files as Artifacts" Evolution**

Historically, Smalltalk's isolation from the file system made version control difficult. This led to the development of **Monticello** and later **Iceberg** (git integration).

* **Tonel:** The community developed **Tonel**, a serialization format that maps Smalltalk code to the file system in a Git-friendly way. A class becomes a directory; a method becomes a file.7  
* **The Inversion:** Crucially, Tonel treats the filesystem as a *derivative* of the image. The user works in the image; when they commit, the system "files out" the code to disk. This proves that "image as truth" can coexist with "files for collaboration".8

### **2.2 Lisp and Scheme: The REPL-Driven Runtime**

Common Lisp and Scheme (Racket) systems operate on similar principles but emphasize the Read-Eval-Print Loop (REPL) as the primary interface.

#### **2.2.1 Image Dumps and Homoiconicity**

Implementations like SBCL allow save-lisp-and-die, creating a binary executable containing the current heap state. This freezes the application state into a static binary.10

* **Homoiconicity:** Lisp code is structured as lists (ASTs) which are native data structures. This allows agents to manipulate code using standard list processing functions (car, cdr), effectively eliminating the parsing step required in other languages. This reduces the cognitive load on a self-modifying agent; it doesn't need to write "syntax," it just constructs logic trees.11

#### **2.2.2 Racket Sandboxes: The Proto-Kernel**

Unlike early Smalltalk, which lacked internal security boundaries (a crash in one object crashed the VM), Racket developed robust **Sandboxed Evaluators**.

* **Resource Limits:** A Racket sandbox allows the creation of an evaluator with strict limits on memory usage and execution time.  
* **Capability Restriction:** The sandbox can be configured to deny access to the filesystem or network (make-evaluator with restricted allow-read lists). This is a critical primitive for sub-agent management, allowing a parent to run untrusted generated code safely.12

### **2.3 The Limitations of Prior Art**

While Smalltalk and Lisp excel at live modification, they historically lack robust **Capability Security**. In a standard Smalltalk image, any object can access global system classes (Smalltalk globals) and potentially corrupt the entire environment. For a multi-agent system where agents might hallucinate destructive code, we need the *liveness* of Smalltalk combined with the *strict isolation* of modern containers.

## ---

**3\. Modern Primitives for Persistence and Isolation**

To realize the HPCAA, we must integrate the philosophy of image-based systems with modern, secure, cloud-native technologies.

### **3.1 Orthogonal Persistence: Agoric SwingSet**

The most relevant modern architectural precedent is **Agoric’s SwingSet** kernel. SwingSet implements **orthogonal persistence** for JavaScript in a distributed context.14

#### **3.1.1 The Vat Model**

SwingSet divides the runtime into **Vats**. A Vat is an isolated unit of synchrony (a heap) that processes messages sequentially.

* **Orthogonal Persistence:** The developer writes standard JavaScript objects. The SwingSet kernel, via a mechanism called the **SwingStore** (typically backed by LMDB or LevelDB), transparently persists the state of all reachable objects. Persistence is not an explicit action; it is a property of the environment. If the host process is killed and restarted, the Vats resume exactly where they left off.15  
* **Reachability:** Persistence is determined by reachability from a "root" object. If an agent holds a reference to a sub-agent, that sub-agent is persisted. This mirrors the garbage collection semantics of memory, applied to disk storage.17

#### **3.1.2 Baggage and Upgrades**

SwingSet introduces the concept of **Baggage** to handle code upgrades. When a Vat is upgraded (its source code changed), the heap is cleared, but the baggage object (a persistent Map) is preserved and passed to the new version of the code. This allows the new agent logic to "rehydrate" its state from the previous version, bridging the gap between image persistence and code evolution.18

### **3.2 WebAssembly (Wasm) and Pyodide Snapshots**

WebAssembly (Wasm) provides the strongest isolation boundary available today short of a full virtual machine, making it the ideal container for untrusted agent code.20

#### **3.2.1 Linear Memory and Snapshots**

A Wasm instance operates on a linear memory buffer. It cannot access the host's memory.

* **Pyodide:** This project ports the CPython interpreter to Wasm. It allows running a full Python environment inside a browser or Node.js process.21  
* **Memory Snapshots:** Pyodide has experimental support for make\_memory\_snapshot(). This function dumps the entire Wasm linear memory to a binary blob. This snapshot captures the exact state of the Python interpreter: loaded libraries, global variables, and even the execution stack.22  
* **Implications:** This enables a "fork" operation for agents. To spawn a sub-agent, the system can snapshot the parent's Wasm memory and instantiate a new Wasm instance from that snapshot. This is instant cloning of a running process.21

### **3.3 Closure Serialization and Resumability**

A challenge in JS/Python agents is serializing **Closures**—functions that capture variables from their surrounding scope. Standard JSON serialization fails here.24

#### **3.3.1 Qwik's QRLs**

The **Qwik** web framework introduces **QRLs (Qwik URLs)**. The Qwik optimizer analyzes source code and transforms closures into serializable symbols. It explicitly captures the lexical scope (the variables needed by the function) and serializes them.

* **Resumability:** This allows a process to pause on the server and resume on the client without re-executing initialization logic.26  
* **Application:** For agents, this means an agent's "thought process" (a chain of callbacks or promises) can be serialized to disk while waiting for a long-running operation (like an LLM inference), freeing up system resources.28

#### **3.3.2 Python's dill and cloudpickle**

In the Python ecosystem, the pickle module is standard but limited. Libraries like **dill** and **cloudpickle** extend pickling to handle lambdas, closures, and even entire module sessions.

* **Interpreter Session Saving:** dill can serialize the entire state of an interpreter session.29 This is the closest Python equivalent to a Smalltalk image save. However, unpickling untrusted data is a massive security risk, necessitating the Wasm sandbox wrapper.24

## ---

**4\. Architectural Design: The Hyper-Persistent Containerized Agent Architecture (HPCAA)**

Based on the analysis of prior art and modern capabilities, we define the **Hyper-Persistent Containerized Agent Architecture**. This architecture inverts the traditional relationship between code and state.

### **4.1 System Metaphor: The Persistent Kernel**

The system operates as a **Persistent Kernel**. The Kernel manages a collection of **Vats**. Each Vat is an isolated memory region containing one or more Agents. The Kernel is responsible for scheduling execution, facilitating message passing between Vats, and managing the persistence of Vats to the **System Image** (a database or binary log).

### **4.2 Layer 1: The Kernel (The Runtime Host)**

* **Technology Stack:** Node.js (utilizing SES) or Rust (utilizing Wasmtime).  
* **Responsibilities:**  
  * **Vat Management:** Spawning, freezing, thawing, and terminating Vats.  
  * **Capability Router:** Agents cannot talk to the "world" (filesystem, network). They send messages to the Kernel. The Kernel checks the agent's permissions (capabilities) and routes the request.30  
  * **Persistence Manager:** Writes the state of Vats to the underlying storage engine (LSM-Tree like LevelDB).16

### **4.3 Layer 2: The Agent Vats (The Living State)**

This is where the agents live. The design of the Vat depends on the desired language ecosystem (Python vs. JavaScript).

#### **Option A: The Python/Wasm Vat (High Isolation)**

For AI agents, Python is the lingua franca.

* **Container:** Each Vat is a **Pyodide** instance running inside the Kernel.  
* **Persistence Mechanism:** **Snapshotting**. The Kernel periodically pauses the Wasm instance and calls make\_memory\_snapshot(), saving the binary blob to the Image Store.  
* **Self-Modification:** The Agent generates Python source strings and executes them using exec() or importlib.reload(). Since the Wasm memory is the source of truth, these changes are persistent immediately. The "file" the agent thinks it is editing is actually a virtual file in the Wasm MEMFS.31

#### **Option B: The SES/SwingSet Vat (High Integration)**

For high-concurrency coordination agents.

* **Container:** Each Vat is an **SES Compartment**.32  
* **Persistence Mechanism:** **Orthogonal Persistence**. The Kernel intercepts all object writes and persists reachable objects to the SwingStore.  
* **Self-Modification:** Agents use compartment.evaluate() to redefine their behavior. The new function objects are automatically tracked by the persistence layer.14

### **4.4 Layer 3: The Artifact Projector (The Reverse Compiler)**

This is the component that satisfies the user's requirement: "files are derived artifacts."

#### **4.4.1 Concept**

The Projector is a daemon that observes the runtime state. When an agent stabilizes (or upon human request), the Projector "hydrates" the object graph into a directory of source files. This is the inverse of a build system.

#### **4.4.2 The Projection Pipeline**

1. **Traversal:** The Projector walks the agent's object graph (Vat).  
2. **Code Extraction:**  
   * **Python:** Uses inspect.getsource(function) to retrieve the source code of function objects.29  
   * **JavaScript:** Uses Function.prototype.toString() to retrieve the source.  
3. **State Serialization:** Data objects (memories, configs) are serialized to JSON/YAML using cycle-safe serializers (e.g., **serializejson** 34 or **JSOG** 35).  
4. **Formatting:** The code and data are arranged into a standard directory structure (e.g., AgentName/src/behavior.py, AgentName/memory.json).  
5. **Version Control:** These files are committed to a Git repository by the Kernel.

#### **4.4.3 Bidirectional Sync (Hot-Patching)**

If a human developer edits the projected files and pushes to Git, the Kernel must update the runtime.

1. **Diff Detection:** The Kernel detects changes in the AgentName/src/ directory.  
2. **Live Update:** The Kernel injects the new code into the running Vat.  
   * *Smalltalk Style:* It recompiles the method and swaps the pointer in the class definition.  
   * *Agoric Style:* It triggers a "Vat Upgrade," passing the old state (baggage) to the new code to re-initialize.19

## ---

**5\. Detailed Design: The Sub-Agent Hierarchy**

Agents must be able to spawn sub-agents to delegate tasks. This requires a hierarchical Vat management system.

### **5.1 Recursive Compartmentalization**

The architecture supports nesting. A Root Agent can request the Kernel to spawn a Child Vat.

1. **Request:** Root Agent calls Kernel.spawnChild(capabilities).  
2. **Instantiation:** Kernel creates a new, empty Vat.  
3. **Endowment:** The Root Agent passes a subset of its capabilities to the Child. Ideally, this follows the **Principle of Least Authority (POLA)**. If the Root has NetworkAccess, it might grant the Child NetworkAccess(only="google.com"). This capability attenuation is enforced by the Kernel's proxy wrappers.36

### **5.2 Supervision and VIGIL**

Self-modifying sub-agents are prone to instability (e.g., rewriting code into an infinite loop or syntax error). We integrate the **VIGIL** pattern 38 for supervision.

* **Observation Layer:** The Kernel logs all exceptions, resource usage, and "emotions" (internal state metrics) of the Child Vat.  
* **Reflection Layer:** The Parent Agent monitors this stream. It does not just watch for crashes; it watches for *deviant behavior* (e.g., looping, stagnating).  
* **Intervention:** If the Child fails, the Parent can:  
  1. **Restart:** Kill the Vat and restore from the last known good Snapshot.  
  2. **Lobotomize:** Restore the Vat but revoke specific capabilities.  
  3. **Debug:** Freeze the Child Vat and inspect its memory image to determine why the self-modification failed.

## ---

**6\. Implementation Specifications**

### **6.1 Persistence Data Structures**

To support "files as artifacts," the runtime data structures must be serializable.

#### **6.1.1 Handling Cycles**

Agent memory graphs are cyclic (Agent \-\> Task \-\> Agent).

* **Problem:** JSON.stringify throws TypeError: cyclic object value.39  
* **Solution:** Use **Cycle-Aware Serializers**.  
  * *JS:* **JSOG (JavaScript Object Graph)** uses @id and @ref tags to denote references.35  
  * *Python:* **jsonpickle** or **serializejson** encodes the object graph structure, handling cycles and preserving type information (e.g., {"py/object": "module.ClassName"}).40

#### **6.1.2 Persistence Format: STON**

We recommend adopting a format similar to **STON (Smalltalk Object Notation)**.41 STON is designed for image-based systems. It is human-readable (like JSON) but supports:

* **Class Tags:** Point\[1, 2\] instead of {"x":1, "y":2}.  
* **References:** @1 to refer to a previously serialized object (handling cycles).  
* Symbols: Native support for canonical strings.  
  Adopting STON (or a JSON-compatible variant) ensures that the "Artifact Projector" produces files that are actually readable and editable by humans, satisfying the "derived artifact" requirement.

### **6.2 Security Boundaries: The Sandbox Problem**

#### **6.2.1 The Danger of eval()**

Self-modification requires eval() (JS) or exec() (Python). In a standard environment, this is a security hole.

* **Python solution:** **RestrictedPython** allows defining a subset of the language (blocking \_\_import\_\_, os, etc.).42 However, it is fragile. **Pyodide/Wasm** is the superior solution because the isolation is at the memory/instruction level. Even if the agent manages to execute malicious bytecode, it can only affect its own linear memory, not the host Kernel.43  
* **JS solution:** **SES (Secure EcmaScript)**. By calling lockdown(), SES freezes all shared intrinsics (Object.prototype, Array.prototype). An agent running in a Compartment cannot modify the global environment or access host capabilities unless explicitly endowed.32

## ---

**7\. Comparative Analysis of Implementation Stacks**

Two distinct paths exist for implementing HPCAA.

| Feature | Stack A: Python / Wasm (Pyodide) | Stack B: JS / SES (Agoric SwingSet) |
| :---- | :---- | :---- |
| **Primary Language** | Python (Native AI libraries) | JavaScript (Hardened) |
| **Isolation Mechanism** | **Strong:** Wasm Memory Isolation | **Logical:** Language-level Compartments |
| **Persistence Model** | **Snapshot:** Dump entire heap to binary blob 22 | **Orthogonal:** DB intercepts object writes 15 |
| **Self-Modification** | exec(), importlib.reload | eval(), new Compartment() |
| **Sub-Agent Cost** | High (New Python Interpreter \~10MB) | Low (New Compartment \~KB) |
| **Artifact Projection** | Custom script using inspect | Custom serializer traversing baggage |
| **Suitability** | Best for **LLM/AI-heavy** agents requiring PyTorch/NumPy | Best for **Coordination/Logic** agents requiring high concurrency |

**Recommendation:** For a general-purpose AI agent system, **Stack A (Python/Wasm)** is preferable due to the dominance of Python in AI. The overhead of Wasm snapshots is acceptable for the benefit of running unmodified Python AI libraries. For purely logical/economic agents, Stack B is superior.

## ---

**8\. Case Study: The Lifecycle of a Self-Modifying Agent**

To illustrate the HPCAA in action, we trace the lifecycle of an agent named "Optimizer."

1. **Genesis (Boot):** The Kernel instantiates a new Pyodide Vat. It loads the "Optimizer" image (snapshot) from the database.  
2. **Introspection:** Optimizer analyzes its own sort\_data method. It queries an LLM: "Rewrite this function to be O(n log n)."  
3. **Sandbox Test:**  
   * Optimizer requests a **Ephemeral Child Vat** from the Kernel.  
   * It loads the new code candidate into the Child.  
   * It runs unit tests against the Child.  
4. **Self-Modification:**  
   * Tests pass. Optimizer calls self.update\_code('sort\_data', new\_code\_string).  
   * The Runtime executes exec() to redefine the function in the live memory.  
   * *Crucially:* The old function object is kept in a history list (self.history) for rollback capability.  
5. **Persistence:** The Kernel detects the memory change. At the end of the "crank," it takes a differential snapshot of the Wasm memory (or simply logs the state change if using event sourcing).44  
6. **Projection:** The ArtifactProjector detects the change. It decompiles the new sort\_data function and writes it to agents/optimizer/src/sorting.py. It commits this to the git repo with the message "Auto-update: Optimized sorting."

## ---

**9\. Challenges and Future Directions**

### **9.1 The "Git-Diff" Problem**

When "files are derived artifacts," a change in the runtime might produce a massive diff in the files if the serializer is not deterministic.

* **Solution:** Canonical Serialization. The Projector must sort keys, enforce deterministic ordering of unordered collections (Sets/Maps), and use consistent formatting (Prettier/Black) to ensure that a small change in logic results in a small change in the file artifact.35

### **9.2 Debugging the Image**

Debugging a binary blob is notoriously difficult.

* **Solution:** Source Maps. The Projector must maintain a precise map between the objects in the heap and the lines of code in the derived files. When an exception occurs in the Vat, the Kernel uses these maps to translate the Wasm stack trace back to the "virtual" source files the developer sees.45

### **9.3 Conclusion**

The **Hyper-Persistent Containerized Agent Architecture** represents a necessary evolution for the next generation of AI agents. By moving the "source of truth" from the filesystem to the runtime image, we eliminate the friction of deployment and enable true recursive self-improvement. Through the use of **WebAssembly** for isolation, **Pyodide** for runtime support, and **Projectors** for artifact generation, we can build systems that are as fluid and adaptive as biological intelligence, while retaining the safety and auditability of modern software engineering.

The "Image" is no longer a black box; it is the transparent, persistent soul of the agent, and the file system is merely its shadow.

## ---

**10\. References and Citations Summary**

* **Smalltalk/Image Persistence:** 4  
* **Tonel/FileTree (Files as Artifacts):** 7  
* **Agoric SwingSet/Persistence:** 14  
* **WebAssembly/Pyodide Snapshots:** 21  
* **Security (SES, RestrictedPython):** 12  
* **Serialization (QRL, Cycles, STON):** 35  
* **Supervision (VIGIL):** 38

#### **Works cited**

1. Self-Modifying AI Agents: The Future of Software Development \- Spiral Scout, accessed January 11, 2026, [https://spiralscout.com/blog/self-modifying-ai-software-development](https://spiralscout.com/blog/self-modifying-ai-software-development)  
2. Exploratory data analysis with Pharo Smalltalk \- Connor Skennerton, accessed January 11, 2026, [https://ctskennerton.github.io/2020/12/10/exploratory-data-analysis-with-pharo-smalltalk/](https://ctskennerton.github.io/2020/12/10/exploratory-data-analysis-with-pharo-smalltalk/)  
3. Pharo \- How do I share static resources in version control? \- Stack Overflow, accessed January 11, 2026, [https://stackoverflow.com/questions/38799507/pharo-how-do-i-share-static-resources-in-version-control](https://stackoverflow.com/questions/38799507/pharo-how-do-i-share-static-resources-in-version-control)  
4. Design Principles for a High-Performance Smalltalk \- CEUR-WS.org, accessed January 11, 2026, [https://ceur-ws.org/Vol-3325/regular2.pdf](https://ceur-ws.org/Vol-3325/regular2.pdf)  
5. \[ANN\] Improving dialect portability and git support \- Google Groups, accessed January 11, 2026, [https://groups.google.com/g/va-smalltalk/c/U4HVPl0KVrc/m/9LoXecwHGgAJ](https://groups.google.com/g/va-smalltalk/c/U4HVPl0KVrc/m/9LoXecwHGgAJ)  
6. mumez/smalltalk-dev-plugin: Claude Code plugin for AI-driven Smalltalk (Pharo) development \- GitHub, accessed January 11, 2026, [https://github.com/mumez/smalltalk-dev-plugin](https://github.com/mumez/smalltalk-dev-plugin)  
7. Pharo project on Git \- Stack Overflow, accessed January 11, 2026, [https://stackoverflow.com/questions/25722280/pharo-project-on-git](https://stackoverflow.com/questions/25722280/pharo-project-on-git)  
8. How to serialize and load an object in SBCL/Common Lisp \- Stack Overflow, accessed January 11, 2026, [https://stackoverflow.com/questions/39555363/how-to-serialize-and-load-an-object-in-sbcl-common-lisp](https://stackoverflow.com/questions/39555363/how-to-serialize-and-load-an-object-in-sbcl-common-lisp)  
9. CL, Clojure or Racket? : r/lisp \- Reddit, accessed January 11, 2026, [https://www.reddit.com/r/lisp/comments/1ptsrag/cl\_clojure\_or\_racket/](https://www.reddit.com/r/lisp/comments/1ptsrag/cl_clojure_or_racket/)  
10. 14.12 Sandboxed Evaluation \- Racket Documentation, accessed January 11, 2026, [https://docs.racket-lang.org/reference/Sandboxed\_Evaluation.html](https://docs.racket-lang.org/reference/Sandboxed_Evaluation.html)  
11. Developing/improving security sandboxes with Racket \- General, accessed January 11, 2026, [https://racket.discourse.group/t/developing-improving-security-sandboxes-with-racket/3976](https://racket.discourse.group/t/developing-improving-security-sandboxes-with-racket/3976)  
12. The Agoric Platform \- Agoric Documentation, accessed January 11, 2026, [https://docs.agoric.com/guides/platform/](https://docs.agoric.com/guides/platform/)  
13. agoric-sdk/packages/SwingSet/docs/virtual-objects.md at master \- GitHub, accessed January 11, 2026, [https://github.com/Agoric/agoric-sdk/blob/master/packages/SwingSet/docs/virtual-objects.md](https://github.com/Agoric/agoric-sdk/blob/master/packages/SwingSet/docs/virtual-objects.md)  
14. agoric-sdk/CHANGELOG.md at master \- GitHub, accessed January 11, 2026, [https://github.com/Agoric/agoric-sdk/blob/master/CHANGELOG.md](https://github.com/Agoric/agoric-sdk/blob/master/CHANGELOG.md)  
15. Glossary \- Agoric Documentation, accessed January 11, 2026, [https://docs.agoric.com/glossary/](https://docs.agoric.com/glossary/)  
16. Contract Upgrade \- Agoric Documentation, accessed January 11, 2026, [https://docs.agoric.com/guides/zoe/contract-upgrade](https://docs.agoric.com/guides/zoe/contract-upgrade)  
17. agoric-sdk/packages/SwingSet/docs/vat-upgrade.md at master \- GitHub, accessed January 11, 2026, [https://github.com/Agoric/agoric-sdk/blob/master/packages/SwingSet/docs/vat-upgrade.md](https://github.com/Agoric/agoric-sdk/blob/master/packages/SwingSet/docs/vat-upgrade.md)  
18. WebAssembly concepts \- MDN Web Docs, accessed January 11, 2026, [https://developer.mozilla.org/en-US/docs/WebAssembly/Guides/Concepts](https://developer.mozilla.org/en-US/docs/WebAssembly/Guides/Concepts)  
19. Run Real Python in Browsers With Pyodide and WebAssembly \- The New Stack, accessed January 11, 2026, [https://thenewstack.io/run-real-python-in-browsers-with-pyodide-and-webassembly/](https://thenewstack.io/run-real-python-in-browsers-with-pyodide-and-webassembly/)  
20. Exporting and importing a Pyodide instance to/from a .wasm file / Grant Nestor | Observable, accessed January 11, 2026, [https://observablehq.com/@gnestor/exporting-and-importing-a-pyodide-instance-to-from-a-wasm-fi](https://observablehq.com/@gnestor/exporting-and-importing-a-pyodide-instance-to-from-a-wasm-fi)  
21. Contents of Release Files could be explained · Issue \#4942 · pyodide/pyodide \- GitHub, accessed January 11, 2026, [https://github.com/pyodide/pyodide/issues/4942](https://github.com/pyodide/pyodide/issues/4942)  
22. pickle — Python object serialization — Python 3.14.2 documentation, accessed January 11, 2026, [https://docs.python.org/3/library/pickle.html](https://docs.python.org/3/library/pickle.html)  
23. Python serialize lexical closures? \- Stack Overflow, accessed January 11, 2026, [https://stackoverflow.com/questions/573569/python-serialize-lexical-closures](https://stackoverflow.com/questions/573569/python-serialize-lexical-closures)  
24. Passing Closures | Tutorial Qwik Documentation, accessed January 11, 2026, [https://qwik.dev/tutorial/props/closures/](https://qwik.dev/tutorial/props/closures/)  
25. Optimizer | Tutorial Qwik Documentation, accessed January 11, 2026, [https://qwik.dev/tutorial/qrl/optimizer/](https://qwik.dev/tutorial/qrl/optimizer/)  
26. "Qwik's magic is not in how fast it executes, but how good it is in avoiding doing any work", accessed January 11, 2026, [https://devm.io/javascript/qwik-javascript-hevery](https://devm.io/javascript/qwik-javascript-hevery)  
27. dill \- PyPI, accessed January 11, 2026, [https://pypi.org/project/dill/](https://pypi.org/project/dill/)  
28. How does a sandbox module know the difference between trusted and untrusted code, accessed January 11, 2026, [https://security.stackexchange.com/questions/176758/how-does-a-sandbox-module-know-the-difference-between-trusted-and-untrusted-code](https://security.stackexchange.com/questions/176758/how-does-a-sandbox-module-know-the-difference-between-trusted-and-untrusted-code)  
29. Dealing with the file system — Version 0.29.0 \- Pyodide, accessed January 11, 2026, [https://pyodide.org/en/stable/usage/file-system.html](https://pyodide.org/en/stable/usage/file-system.html)  
30. ses \- NPM, accessed January 11, 2026, [http://www.npmjs.com/package/ses](http://www.npmjs.com/package/ses)  
31. SES (Secure EcmaScript) details, accessed January 11, 2026, [https://www.proposals.es/proposals/SES%20(Secure%20EcmaScript)](https://www.proposals.es/proposals/SES%20\(Secure%20EcmaScript\))  
32. serializejson \- PyPI, accessed January 11, 2026, [https://pypi.org/project/serializejson/](https://pypi.org/project/serializejson/)  
33. jsog/jsog: JavaScript Object Graph \- GitHub, accessed January 11, 2026, [https://github.com/jsog/jsog](https://github.com/jsog/jsog)  
34. endo/packages/ses/docs/guide.md at master \- GitHub, accessed January 11, 2026, [https://github.com/endojs/endo/blob/master/packages/ses/docs/guide.md](https://github.com/endojs/endo/blob/master/packages/ses/docs/guide.md)  
35. Hardened JavaScript | Agoric Documentation, accessed January 11, 2026, [https://docs.agoric.com/guides/js-programming/hardened-js](https://docs.agoric.com/guides/js-programming/hardened-js)  
36. VIGIL: A Reflective Runtime for Self-Healing LLM Agents \- arXiv, accessed January 11, 2026, [https://arxiv.org/html/2512.07094v2](https://arxiv.org/html/2512.07094v2)  
37. TypeError: cyclic object value \- JavaScript \- MDN Web Docs \- Mozilla, accessed January 11, 2026, [https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Cyclic\_object\_value](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Cyclic_object_value)  
38. jsonpickle documentation, accessed January 11, 2026, [https://jsonpickle.github.io/](https://jsonpickle.github.io/)  
39. ston/ston-paper.md at master · svenvc/ston \- GitHub, accessed January 11, 2026, [https://github.com/svenvc/ston/blob/master/ston-paper.md](https://github.com/svenvc/ston/blob/master/ston-paper.md)  
40. CVE-2024-47532 Detail \- NVD, accessed January 11, 2026, [https://nvd.nist.gov/vuln/detail/CVE-2024-47532](https://nvd.nist.gov/vuln/detail/CVE-2024-47532)  
41. Security \- WebAssembly, accessed January 11, 2026, [https://webassembly.org/docs/security/](https://webassembly.org/docs/security/)  
42. Events and Snapshots | RavenDB Documentation, accessed January 11, 2026, [https://docs.ravendb.net/6.2/integrations/akka.net-persistence/events-and-snapshots](https://docs.ravendb.net/6.2/integrations/akka.net-persistence/events-and-snapshots)  
43. Weekly Updates \- Agoric, accessed January 11, 2026, [https://papers.agoric.com/weekly-updates/](https://papers.agoric.com/weekly-updates/)  
44. @agoric/swingset-vat \- npm, accessed January 11, 2026, [https://www.npmjs.com/package/@agoric/swingset-vat](https://www.npmjs.com/package/@agoric/swingset-vat)  
45. Running Python in the Browser with Pyodide: A Comprehensive Guide \- Jnaapti, accessed January 11, 2026, [https://jnaapti.com/articles/article/running-python-in-browser-with-pyodide](https://jnaapti.com/articles/article/running-python-in-browser-with-pyodide)