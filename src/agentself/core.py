"""Core abstractions for the capability-based agent system.

This module defines the fundamental types used throughout the system:
- CapabilityContract: What a capability declares it might do
- CapabilityCall: A recorded call to a capability method
- ExecutionPlan: The result of analyzing code before execution
- ExecutionResult: The result of actually executing code
- ExecutionMode: Whether we're recording or executing
- PermissionStrategy: How to handle permission for a capability
"""

from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionMode(Enum):
    """Mode for sandbox execution."""

    RECORD = "record"
    """Use proxies to record what capabilities would be used, without side effects."""

    EXECUTE = "execute"
    """Use real capabilities, side effects occur."""


class PermissionStrategy(Enum):
    """How to handle permission checking for a capability.

    Different strategies offer different trade-offs between security and usability.
    """

    PRE_APPROVED = "pre_approved"
    """User trusts this capability entirely. All calls auto-allowed."""

    CONTRACT_BASED = "contract_based"
    """User approves the contract upfront. Calls matching contract auto-allowed."""

    CALL_BY_CALL = "call_by_call"
    """Each invocation prompts for approval (the proxy model)."""

    BUDGET_BASED = "budget_based"
    """Limited scope without constant prompting (e.g., 'up to 10 file writes')."""

    AUDIT_ONLY = "audit_only"
    """Execute immediately, log for review. High-trust contexts only."""


@dataclass
class CapabilityContract:
    """What a capability declares it might do.

    Contracts enable pre-approval: the user approves what a capability *can* do
    upfront, rather than approving each individual call. This solves the
    fundamental limitation of proxy-based call-by-call approval, where code
    with control flow depending on capability results can't be accurately recorded.

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
        """Check if a resource matches a pattern.

        Supports glob-style patterns:
        - "*" matches any single path component
        - "**" matches any number of path components
        """
        # Handle ** by converting to fnmatch-compatible pattern
        fnmatch_pattern = pattern.replace("**", "*")
        return fnmatch.fnmatch(resource, fnmatch_pattern)

    def merge(self, other: "CapabilityContract") -> "CapabilityContract":
        """Merge two contracts, taking the union of all permissions.

        Useful when composing capabilities.
        """
        return CapabilityContract(
            reads=list(set(self.reads + other.reads)),
            writes=list(set(self.writes + other.writes)),
            executes=list(set(self.executes + other.executes)),
            network=list(set(self.network + other.network)),
            spawns=self.spawns or other.spawns,
        )

    def restrict(self, restrictions: "CapabilityContract") -> "CapabilityContract":
        """Create a new contract that is the intersection with restrictions.

        Useful when deriving a more restricted capability.
        """
        # For simplicity, take the more restrictive patterns
        # A full implementation would compute actual intersections
        return CapabilityContract(
            reads=[r for r in self.reads if r in restrictions.reads] or self.reads,
            writes=[w for w in self.writes if w in restrictions.writes] or [],
            executes=[e for e in self.executes if e in restrictions.executes] or [],
            network=[n for n in self.network if n in restrictions.network] or [],
            spawns=self.spawns and restrictions.spawns,
        )

    def is_subset_of(self, other: "CapabilityContract") -> bool:
        """Check if this contract's permissions are a subset of another's.

        Useful for verifying that a derived capability doesn't exceed
        the parent's permissions.
        """
        # Simplified check - a full implementation would handle pattern matching
        if self.spawns and not other.spawns:
            return False

        for resource in self.reads:
            if not other.covers("reads", resource):
                return False
        for resource in self.writes:
            if not other.covers("writes", resource):
                return False
        for resource in self.executes:
            if not other.covers("executes", resource):
                return False
        for resource in self.network:
            if not other.covers("network", resource):
                return False

        return True


@dataclass
class CapabilityCall:
    """A single call to a capability method.

    Recorded during RECORD mode to show what the code intends to do.
    """

    capability_name: str
    """Name of the capability being called (e.g., 'fs', 'cmd')."""

    method_name: str
    """Name of the method being called (e.g., 'read', 'write')."""

    args: tuple
    """Positional arguments to the method."""

    kwargs: dict
    """Keyword arguments to the method."""

    timestamp: float = field(default_factory=time.time)
    """When this call was recorded."""

    def __str__(self) -> str:
        """Human-readable representation of the call."""
        args_str = ", ".join(repr(a) for a in self.args)
        kwargs_str = ", ".join(f"{k}={v!r}" for k, v in self.kwargs.items())
        all_args = ", ".join(filter(None, [args_str, kwargs_str]))
        return f"{self.capability_name}.{self.method_name}({all_args})"

    def matches(self, capability: str = None, method: str = None) -> bool:
        """Check if this call matches the given filters."""
        if capability and self.capability_name != capability:
            return False
        if method and self.method_name != method:
            return False
        return True


@dataclass
class ExecutionPlan:
    """The result of a RECORD-mode execution.

    Shows what the code intends to do without actually doing it.
    This enables the permission system to approve/deny before execution.
    """

    code: str
    """The code that was analyzed."""

    calls: list[CapabilityCall] = field(default_factory=list)
    """Capability calls that would be made."""

    success: bool = True
    """Whether the code could be analyzed (syntax ok, etc.)."""

    error: str | None = None
    """Error message if analysis failed."""

    variables_accessed: set[str] = field(default_factory=set)
    """Variables the code reads from."""

    variables_defined: set[str] = field(default_factory=set)
    """Variables the code defines."""

    def __str__(self) -> str:
        """Human-readable summary of the plan."""
        if not self.success:
            return f"Plan failed: {self.error}"

        if not self.calls:
            return "Plan: (no capability calls)"

        lines = ["Plan:"]
        for i, call in enumerate(self.calls, 1):
            lines.append(f"  {i}. {call}")
        return "\n".join(lines)

    def has_writes(self) -> bool:
        """Check if any calls are write operations."""
        write_methods = {"write", "mkdir", "run", "execute", "delete", "remove"}
        return any(call.method_name in write_methods for call in self.calls)

    def capabilities_used(self) -> set[str]:
        """Get the set of capability names used."""
        return {call.capability_name for call in self.calls}


@dataclass
class ExecutionResult:
    """The result of executing code in the sandbox."""

    success: bool
    """Whether execution completed without errors."""

    output: str = ""
    """Captured stdout from execution."""

    error: str = ""
    """Error message if execution failed."""

    return_value: Any = None
    """Return value if the code was an expression."""

    calls: list[CapabilityCall] = field(default_factory=list)
    """Capability calls that were made during execution."""

    plan: ExecutionPlan | None = None
    """The plan that was approved before execution."""

    permission_denied: bool = False
    """True if execution was blocked by permission handler."""

    def __str__(self) -> str:
        """Format as readable output."""
        if self.permission_denied:
            return f"Permission denied: {self.error}"

        if self.success:
            parts = []
            if self.output:
                parts.append(self.output.rstrip())
            if self.return_value is not None:
                parts.append(f"=> {self.return_value!r}")
            return "\n".join(parts) if parts else "(no output)"
        else:
            return f"Error: {self.error}"


@dataclass
class DependencyInfo:
    """Tracks dependencies between code blocks and capabilities.

    Enables understanding the "blast radius" of changes.
    """

    # Maps variable name -> list of (block_index, capability_calls that produced it)
    variable_sources: dict[str, list[tuple[int, list[CapabilityCall]]]] = field(
        default_factory=dict
    )

    # Maps capability name -> list of block indices that use it
    capability_users: dict[str, list[int]] = field(default_factory=dict)

    # Maps block_index -> variables it depends on
    block_dependencies: dict[int, set[str]] = field(default_factory=dict)

    def record_block(
        self,
        block_index: int,
        plan: ExecutionPlan,
    ) -> None:
        """Record dependency information for a code block."""
        # Track variables defined
        for var in plan.variables_defined:
            if var not in self.variable_sources:
                self.variable_sources[var] = []
            self.variable_sources[var].append((block_index, plan.calls.copy()))

        # Track capabilities used
        for cap_name in plan.capabilities_used():
            if cap_name not in self.capability_users:
                self.capability_users[cap_name] = []
            self.capability_users[cap_name].append(block_index)

        # Track variable dependencies
        self.block_dependencies[block_index] = plan.variables_accessed.copy()

    def get_affected_by_capability_change(self, capability_name: str) -> list[int]:
        """Get block indices that would be affected if a capability changes."""
        return self.capability_users.get(capability_name, [])

    def get_variable_origin(self, variable_name: str) -> list[CapabilityCall]:
        """Get the capability calls that produced a variable."""
        sources = self.variable_sources.get(variable_name, [])
        if not sources:
            return []
        # Return calls from the most recent definition
        _, calls = sources[-1]
        return calls
