# Agent Architecture

Migrated and condensed from:
- `.specs/00 Bootstrap/Design.md`
- `.specs/00 Bootstrap/2026-01-11 Agent Architecture Research and Design.md`

## Core premise
- Runtime is primary; source files are a serialization format.
- REPL-first agents trade orchestration for live programming.
- Capabilities are in-process objects with contracts.

## REPL-first vs terminal-first
- **Pros**: Python fluency, state persistence, composability, rich errors.
- **Cons**: subprocess complexity, Python lock-in, security surface, auditability.

## Image vs source models
- **Image model**: live state is truth; easy runtime mutation, hard diff/merge.
- **Source model**: files are truth; easy diff/merge, hard live evolution.
- **Hybrid**: runtime edits + “dehydrate” to source for versioning.

## Reactive notebook influence
- Dependency DAG, selective re-execution, explicit blast radius.
- Supports non-destructive exploration and structural visibility.

## FastMCP insight
- Minimal ceremony tool definition aligns with “self-programming.”
- REPL can act as a growing MCP server.

## Capability model
- Capabilities are stateful objects with self-described contracts.
- Contracts allow pre-approval vs call-by-call proxies.
- Derivable and revocable by design.

## Research directions (HPCAA)
- Persistent vats (image-like state) + projector to file artifacts.
- Isolation via Wasm or hardened sandboxes.
- Orthogonal persistence (SwingSet-like) and snapshotting.

## Open questions
- Contract verification vs actual behavior.
- Versioning and upgrade semantics for capabilities.
- Cross-agent delegation and trust boundaries.
- Audit logging at scale.
