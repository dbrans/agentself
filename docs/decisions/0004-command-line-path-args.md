# ADR 0004: Command Line Path-Arg Guardrails

## Status
Accepted (2026-01-13)

## Context
Allowlisted commands could still access arbitrary paths (e.g., `ls /`) via arguments.

## Decision
Add `allowed_paths` to `CommandLineCapability` and validate path-like arguments against allowed roots.

## Alternatives
- Restrict cwd only.
- Switch to `shell=False` with full argv parsing.

## Consequences
- Safer defaults without heavy sandboxing.
- Consistent validation reusable by other capabilities.
