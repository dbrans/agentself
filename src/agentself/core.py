"""Core types for the capability-based agent system.

This module defines fundamental types:
- CapabilityContract: What a capability declares it might do
- ExecutionResult: Result of executing code
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CapabilityContract:
    """What a capability declares it might do.

    Contracts enable pre-approval: the user approves what a capability *can* do
    upfront, rather than approving each individual call.

    Resource patterns use a simple glob-like syntax:
    - "file:*.py" - any Python file
    - "file:src/**" - anything under src/
    - "shell:git *" - any git command
    - "https://api.example.com/*" - any URL under that domain

    Example:
        contract = CapabilityContract(
            reads=["file:*.py", "file:*.md"],
            writes=["file:src/**"],
            executes=["shell:git *", "shell:pytest *"],
        )
    """

    reads: list[str] = field(default_factory=list)
    """Resources this capability might read (e.g., ["file:*.py", "env:HOME"])."""

    writes: list[str] = field(default_factory=list)
    """Resources this capability might modify (e.g., ["file:src/*"])."""

    executes: list[str] = field(default_factory=list)
    """Commands/actions this capability might execute (e.g., ["shell:git *"])."""

    network: list[str] = field(default_factory=list)
    """Network resources accessed (e.g., ["https://api.example.com/*"])."""

    spawns: bool = False
    """Whether this capability might create sub-capabilities or agents."""

    def __str__(self) -> str:
        """Human-readable summary of the contract."""
        parts = []
        if self.reads:
            parts.append(f"reads: {self.reads}")
        if self.writes:
            parts.append(f"writes: {self.writes}")
        if self.executes:
            parts.append(f"executes: {self.executes}")
        if self.network:
            parts.append(f"network: {self.network}")
        if self.spawns:
            parts.append("spawns: true")
        return ", ".join(parts) if parts else "(no effects declared)"

    def covers(self, resource_type: str, resource: str) -> bool:
        """Check if this contract covers a specific resource.

        Args:
            resource_type: One of "reads", "writes", "executes", "network".
            resource: The specific resource to check (e.g., "file:src/main.py").

        Returns:
            True if the contract allows access to this resource.
        """
        patterns = getattr(self, resource_type, [])
        return any(self._matches_pattern(pattern, resource) for pattern in patterns)

    def _matches_pattern(self, pattern: str, resource: str) -> bool:
        """Check if a resource matches a pattern."""
        fnmatch_pattern = pattern.replace("**", "*")
        return fnmatch.fnmatch(resource, fnmatch_pattern)

    def merge(self, other: "CapabilityContract") -> "CapabilityContract":
        """Merge two contracts, taking the union of all permissions."""
        return CapabilityContract(
            reads=list(set(self.reads + other.reads)),
            writes=list(set(self.writes + other.writes)),
            executes=list(set(self.executes + other.executes)),
            network=list(set(self.network + other.network)),
            spawns=self.spawns or other.spawns,
        )


@dataclass
class ExecutionResult:
    """Result of executing code in the REPL."""

    success: bool
    """Whether execution completed without errors."""

    stdout: str = ""
    """Captured stdout from execution."""

    stderr: str = ""
    """Captured stderr from execution."""

    return_value: Any = None
    """Return value if the code was an expression (JSON-serializable)."""

    error_type: str | None = None
    """Type of error if execution failed (e.g., 'SyntaxError')."""

    error_message: str | None = None
    """Error message if execution failed."""

    def __str__(self) -> str:
        """Format as readable output."""
        if self.success:
            parts = []
            if self.stdout:
                parts.append(self.stdout.rstrip())
            if self.return_value is not None:
                parts.append(f"=> {self.return_value!r}")
            return "\n".join(parts) if parts else "(no output)"
        else:
            return f"{self.error_type}: {self.error_message}"
