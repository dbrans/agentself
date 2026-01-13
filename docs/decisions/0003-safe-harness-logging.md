# ADR 0003: Harness Logging Scope

## Status
Accepted (2026-01-13)

## Context
Debug logs from third-party libraries were too noisy when root logging was set to DEBUG.

## Decision
Configure logging only for the `agentself` logger tree and keep root at WARNING by default. Provide optional log file and log level flags.

## Alternatives
- Root logger DEBUG with external filters.
- Disable debug logs entirely.

## Consequences
- Useful debug logs without third-party spam.
- Explicit opt-in via env/flags.
