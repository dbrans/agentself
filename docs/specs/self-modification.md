# Self-Modification Layers

Migrated from `.specs/00 Bootstrap/2026-01-11 Self Modify Part 2.md`.

## Summary
- Current system can modify capabilities with workflow, but core infrastructure lacks a safe workflow.
- Proposed graduated trust layers:
  - **Layer 0**: Immutable kernel (security boundary)
  - **Layer 1**: Core modules (restart required)
  - **Layer 2**: Hot‑reload capabilities
  - **Layer 3**: Ephemeral session state

## Proposed CoreSourceCapability
A controlled workflow for core changes:
- Introspect core modules
- Stage edits with validation
- Test in subprocess
- Apply with restart requirement
- Maintain versioned backups

## Principles
- Graduated trust
- Test before apply
- Always rollbackable
- Immutable security kernel

## Gaps identified
- No core modification workflow
- No subprocess testing for core changes
- No immutable kernel
- No integrated versioning
