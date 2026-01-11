# Research Prompt: Language/Environment Selection for Self-Modifying Capability Agent

## Context

We're building a **self-modifying coding agent** with a fundamentally different architecture than existing terminal-first agents (Claude Code, gemini-cli). The core design principles from [Design.md](file:///Users/dbrans/Code/agentself/.specs/00%20Bootstrap/Design.md):

1. **Locked-Down REPL**: Agent lives inside a constrained runtime with no inherent file/network access
2. **Capability Objects**: All powers granted via self-documenting, composable, revocable capability objects (not JSON tool schemas)
3. **Runtime-Primary Model**: The running agent is the source of truth; source files are a serialization format for versioning and transmission (Smalltalk philosophy + git-friendly dehydration)
4. **Self-Development**: Agent can create, test, install, and commit new capabilities via `CapabilityFactory`
5. **Dependency-Aware Structure**: Agent sees its own structure (DAG, symbol table) and understands blast radius of changes

---

## Evaluation Priorities

Rank order for evaluating language/environment choices:

### 1. Iteration and Experimentation Velocity
- How quickly can the agent try things and see results?
- Hot-reload capabilities without restart
- Tight feedback loops for self-modification
- Low ceremony for defining new capabilities

### 2. Versioning, Forking, and Rewinding Modifications
- Can we checkpoint/restore runtime state?
- Is dehydration to diffable text natural in this language?
- Support for speculative execution (fork, try, discard/keep)
- Structural versioning (not just text diffs)

### 3. Leveraging SOTA Model Strengths (Claude Opus 4.5, Gemini 3)
- Training data representation (what has the model seen most?)
- Cognitive alignment (does the syntax match how the model "thinks"?)
- Existing benchmarks and capabilities in this language
- Tool-use patterns the model already understands

---

## Language/Environment Candidates

### 1. Lisp Family (Clojure, Common Lisp, Scheme, Racket)

**Evaluate:**
- **Homoiconicity**: Code-as-data enables runtime introspection and generation. How well do SOTA models leverage this?
- **Macro systems**: Self-modification via macros vs. runtime evaluation
- **Clojure specifics**: JVM interop, immutable data structures, REPL-driven development culture
- **Common Lisp**: CLOS (Common Lisp Object System), image-based development (like Smalltalk), condition/restart system
- **Sandboxing**: How hard is it to create a locked-down Clojure/CL REPL?
- **Model fluency**: Do Claude/Gemini write idiomatic Lisp? Do they understand macro expansion?

**Questions to answer:**
1. What's the model accuracy on Lisp code generation benchmarks vs. Python?
2. How natural is dehydration of Lisp runtime state to diffable source?
3. What's the ecosystem for sandboxed Lisp execution?
4. Can we get structural versioning (s-expression level) rather than text diffs?

---

### 2. Smalltalk Family (Squeak, Pharo, GNU Smalltalk)

**Evaluate:**
- **Image model**: The running system IS the source of truth—this aligns perfectly with our philosophy
- **Live development**: Change anything at runtime, see immediate effects
- **Object capabilities**: Smalltalk's message-passing mirrors our capability model
- **Versioning challenges**: Images are binary blobs—how to get git-friendly diffs?
- **Model fluency**: Do SOTA models know Smalltalk at all? Training data representation?
- **Modern tooling**: Pharo's Tonel format (one method per file) for git integration

**Questions to answer:**
1. Is there enough Smalltalk in training data for models to be fluent?
2. How does Tonel format handle structural versioning?
3. What's the sandboxing story in Squeak/Pharo?
4. Can we teach the model Smalltalk idioms via in-context examples, or is the gap too large?

---

### 3. JavaScript/TypeScript (Node, Bun, Deno)

**Evaluate:**
- **Ubiquity**: Massive training data representation—models are very JS-fluent
- **Runtime flexibility**: `eval`, `new Function`, dynamic property access
- **Sandboxing**: V8 isolates, vm2, Deno's permission system (very aligned with capabilities!)
- **TypeScript**: Static types for self-documentation, but adds compilation step
- **Hot-reload**: Good ecosystem for HMR, but designed for modules not REPLs
- **Async-first**: Everything is promises—does this help or hurt agent reasoning?

**Questions to answer:**
1. How well do models reason about JavaScript's prototype-based OOP vs. class-based?
2. Deno's permission model: Can we map capabilities directly to Deno permissions?
3. What's the state serialization story? Can we checkpoint V8 isolate state?
4. TypeScript in REPL: Is the compilation overhead worth the documentation?

---

### 4. Python (CPython, PyPy)

**Evaluate:**
- **Model fluency**: Highest—this is the lingua franca of AI/ML, most training data
- **Dynamic introspection**: `inspect`, `ast`, `exec`—rich runtime introspection
- **Sandboxing challenges**: RestrictedPython, PyPy sandbox (deprecated), seccomp wrappers
- **Existing work**: Design.md is Python-based, agentlib exists
- **Ecosystem**: Every library exists, including AI/ML integration

**Questions to answer:**
1. Python sandboxing: What's the current best practice? (RestrictedPython? Subprocess + seccomp?)
2. State serialization: Can we pickle arbitrary runtime state for checkpoint/restore?
3. How much of agentlib's architecture translates to other languages?
4. Is the Python-lock-in from Design.md a feature (cognitive alignment) or limitation?

---

## Cross-Cutting Research Questions

### Model Capability Questions
1. **Benchmark comparison**: Code generation accuracy across languages (HumanEval polyglot, MBPP, etc.)
2. **Self-modification fluency**: Can models write code that modifies code in each language?
3. **Debugging capability**: Which language produces errors the model can best interpret and fix?
4. **Structural reasoning**: Can models reason about ASTs/s-expressions better than text?

### Sandboxing & Security Questions
1. **Privilege escalation risk**: Which language has the most proven sandboxing?
2. **Capability granularity**: Which language naturally maps to fine-grained permissions?
3. **Escape hatch risk**: What are the known sandbox bypasses in each environment?

### Versioning & Serialization Questions
1. **Runtime state capture**: Which runtime allows fullest state serialization?
2. **Diff friendliness**: Which serialization produces the most meaningful diffs?
3. **Branching semantics**: Can we fork runtime state for speculative execution?

### Ecosystem & Pragmatics Questions
1. **Developer velocity**: Which environment lets US iterate fastest while building this?
2. **Dependencies**: Which has the best libraries for what we need (LLM clients, parsers, etc.)?
3. **Future-proofing**: Which is most likely to be well-supported in 5 years?

---

## Desired Research Output

For each language/environment, produce:

1. **Capability matrix**: Rate 1-5 on each priority (velocity, versioning, model leverage)
2. **Proof-of-concept sketch**: What would a minimal locked-down REPL + 1 capability look like?
3. **Risk assessment**: What could go wrong? What's the worst-case scenario?

### Synthesis Questions
1. **Hybrid approach**: Could we use multiple languages? (e.g., Clojure for capability definitions, Python for execution?)
2. **Language-agnostic core**: Is there an architecture that's language-independent?
3. **Progressive enhancement**: Start with Python, add Lisp-like structural features via libraries?

---

## References for Research

- HumanEval / MBPP benchmarks for code generation
- Deno permission system documentation
- Pharo/Squeak Tonel format specification
- RestrictedPython documentation
- Clojure REPL-driven development guides
- V8 Isolates / vm2 sandboxing

---

## Success Criteria

The research should enable a confident decision on:

1. **Primary language**: Which language/runtime for the agent's "inner world"
2. **Serialization format**: How we dehydrate runtime state to versionable text  
3. **Sandboxing strategy**: How we lock down the REPL while granting capabilities
4. **Model prompting strategy**: How we help the model write effective code in chosen language

