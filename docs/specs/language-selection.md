# Language/Environment Selection

Migrated from `.specs/00 Bootstrap/Which Language.md`.

## Context
Design a self-modifying agent with:
- Locked-down REPL
- Capability objects (composable, revocable)
- Runtime-primary state, source as serialization
- Self-development loop (create/test/install/commit capabilities)

## Evaluation priorities
1) Iteration velocity
2) Versioning/forking/rewind
3) Model fluency

## Candidates
- Lisp family (homoiconicity, macros)
- Smalltalk (image model, live dev)
- JS/TS (ubiquity, sandboxing via Deno/V8)
- Python (model fluency, introspection)

## Cross-cutting questions
- Sandboxing and capability granularity
- Serialization and diff friendliness
- Model accuracy per language

## Desired output
- Capability matrix (1–5)
- PoC sketch per language
- Risk assessment
