# ADR 0002: Skills Read-only Access

## Status
Accepted (2026-01-13)

## Context
Skills must be discoverable and inspectable without granting special development privileges.

## Decision
Expose a `skills` capability that provides:
- metadata (`list`, `path`, `files`, `show`)
- read-only `skills.fs` / `skills.cmd` scoped to skills roots

## Alternatives
- A standalone CLI for skills.
- Special writable access for skill development.

## Consequences
- Skills development remains a normal dev task (no special permissions).
- REPL can inspect skills without expanding write access.
