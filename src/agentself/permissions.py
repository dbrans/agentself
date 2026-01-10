"""Permission handling for capability-based execution.

The permission system gates capability calls between record and execute phases.
It enables human-in-the-loop approval, automatic policies, and custom handlers.

Key classes:
- PermissionDecision: The result of a permission check
- PermissionRequest: A request to execute a planned set of calls
- PermissionHandler: Protocol for permission checking
- AutoApproveHandler: Approve everything (for testing/trusted contexts)
- InteractiveHandler: Ask the user via console
- PolicyHandler: Rule-based automatic decisions
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Protocol, runtime_checkable

from agentself.core import CapabilityCall, ExecutionPlan


class PermissionDecision(Enum):
    """Result of a permission check."""

    ALLOW = "allow"
    """Allow this specific execution."""

    DENY = "deny"
    """Deny this execution."""

    ALLOW_SESSION = "allow_session"
    """Allow this and similar calls for the rest of the session."""


@dataclass
class PermissionRequest:
    """A request to execute code that uses capabilities.

    Contains the execution plan (what will happen) and context
    for the permission handler to make a decision.
    """

    plan: ExecutionPlan
    """The analyzed code and its intended capability calls."""

    context: dict = field(default_factory=dict)
    """Additional context (e.g., conversation history, user info)."""

    def summary(self) -> str:
        """Get a human-readable summary of what's being requested."""
        if not self.plan.calls:
            return "Execute code with no capability calls"

        lines = [f"Execute code with {len(self.plan.calls)} capability call(s):"]
        for call in self.plan.calls:
            lines.append(f"  - {call}")
        return "\n".join(lines)


@runtime_checkable
class PermissionHandler(Protocol):
    """Protocol for permission handling.

    Implementations decide whether to allow capability calls
    before they happen.
    """

    def check(self, request: PermissionRequest) -> PermissionDecision:
        """Check if the requested execution should be allowed.

        Args:
            request: The permission request containing the plan.

        Returns:
            A PermissionDecision indicating allow/deny.
        """
        ...


class AutoApproveHandler:
    """Approve all permission requests automatically.

    Use for:
    - Testing
    - Trusted contexts
    - When the user has opted out of confirmations
    """

    def check(self, request: PermissionRequest) -> PermissionDecision:
        """Always approve."""
        return PermissionDecision.ALLOW


class AutoDenyHandler:
    """Deny all permission requests automatically.

    Use for:
    - Read-only/analysis mode
    - Testing permission handling
    """

    def check(self, request: PermissionRequest) -> PermissionDecision:
        """Always deny."""
        return PermissionDecision.DENY


class InteractiveHandler:
    """Ask the user via console for each permission request.

    Presents the planned calls and asks for confirmation.
    """

    def __init__(self, default_allow: bool = False):
        """Create an interactive handler.

        Args:
            default_allow: What to do if input is empty or invalid.
        """
        self.default_allow = default_allow
        self._session_allowed: set[tuple[str, str]] = set()  # (capability, method)

    def check(self, request: PermissionRequest) -> PermissionDecision:
        """Ask the user for permission."""
        # Check if all calls are already session-approved
        if self._all_session_approved(request.plan.calls):
            return PermissionDecision.ALLOW

        # Show what will happen
        print("\n" + "=" * 60)
        print("PERMISSION REQUEST")
        print("=" * 60)
        print(request.summary())
        print("-" * 60)
        print("Options: [y]es, [n]o, [a]llow for session")
        print("-" * 60)

        try:
            response = input("Allow? ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return PermissionDecision.DENY

        if response in ("y", "yes"):
            return PermissionDecision.ALLOW
        elif response in ("a", "allow", "session"):
            # Remember these capability+method pairs for the session
            for call in request.plan.calls:
                self._session_allowed.add((call.capability_name, call.method_name))
            return PermissionDecision.ALLOW_SESSION
        elif response in ("n", "no"):
            return PermissionDecision.DENY
        else:
            return PermissionDecision.ALLOW if self.default_allow else PermissionDecision.DENY

    def _all_session_approved(self, calls: list[CapabilityCall]) -> bool:
        """Check if all calls are already session-approved."""
        return all(
            (call.capability_name, call.method_name) in self._session_allowed
            for call in calls
        )

    def reset_session(self) -> None:
        """Clear all session approvals."""
        self._session_allowed.clear()


@dataclass
class PermissionRule:
    """A rule for automatic permission decisions.

    Rules match on capability name, method name, and optionally
    argument patterns.
    """

    capability: str | None = None
    """Capability name to match, or None for any."""

    method: str | None = None
    """Method name to match, or None for any."""

    decision: PermissionDecision = PermissionDecision.ALLOW
    """Decision to return when rule matches."""

    arg_validator: Callable[[tuple, dict], bool] | None = None
    """Optional function to validate args/kwargs. Return True to match."""

    def matches(self, call: CapabilityCall) -> bool:
        """Check if this rule matches a capability call."""
        if self.capability and call.capability_name != self.capability:
            return False
        if self.method and call.method_name != self.method:
            return False
        if self.arg_validator and not self.arg_validator(call.args, call.kwargs):
            return False
        return True


class PolicyHandler:
    """Rule-based permission handler.

    Evaluates calls against a list of rules in order.
    First matching rule wins. If no rules match, uses the default decision.

    Example:
        handler = PolicyHandler(default=PermissionDecision.DENY)
        handler.allow("fs", "read")  # Allow all file reads
        handler.allow("fs", "list")  # Allow listing files
        handler.deny("cmd")          # Deny all command execution
    """

    def __init__(self, default: PermissionDecision = PermissionDecision.DENY):
        """Create a policy handler.

        Args:
            default: Decision when no rules match. DENY is safer.
        """
        self.default = default
        self.rules: list[PermissionRule] = []

    def add_rule(self, rule: PermissionRule) -> "PolicyHandler":
        """Add a rule to the policy."""
        self.rules.append(rule)
        return self

    def allow(
        self,
        capability: str = None,
        method: str = None,
        arg_validator: Callable[[tuple, dict], bool] = None,
    ) -> "PolicyHandler":
        """Add an ALLOW rule."""
        return self.add_rule(
            PermissionRule(
                capability=capability,
                method=method,
                decision=PermissionDecision.ALLOW,
                arg_validator=arg_validator,
            )
        )

    def deny(
        self,
        capability: str = None,
        method: str = None,
        arg_validator: Callable[[tuple, dict], bool] = None,
    ) -> "PolicyHandler":
        """Add a DENY rule."""
        return self.add_rule(
            PermissionRule(
                capability=capability,
                method=method,
                decision=PermissionDecision.DENY,
                arg_validator=arg_validator,
            )
        )

    def check(self, request: PermissionRequest) -> PermissionDecision:
        """Check all calls against the rules.

        All calls must be allowed for the request to be allowed.
        If any call matches a DENY rule, the request is denied.
        """
        if not request.plan.calls:
            return PermissionDecision.ALLOW

        for call in request.plan.calls:
            decision = self._check_call(call)
            if decision == PermissionDecision.DENY:
                return PermissionDecision.DENY

        return PermissionDecision.ALLOW

    def _check_call(self, call: CapabilityCall) -> PermissionDecision:
        """Check a single call against rules."""
        for rule in self.rules:
            if rule.matches(call):
                return rule.decision
        return self.default


class CompositeHandler:
    """Combines multiple handlers with configurable logic.

    Can require all handlers to agree (AND) or any handler to allow (OR).
    """

    def __init__(
        self,
        handlers: list[PermissionHandler],
        require_all: bool = True,
    ):
        """Create a composite handler.

        Args:
            handlers: List of handlers to consult.
            require_all: If True, all must allow (AND). If False, any allows (OR).
        """
        self.handlers = handlers
        self.require_all = require_all

    def check(self, request: PermissionRequest) -> PermissionDecision:
        """Check with all handlers."""
        decisions = [h.check(request) for h in self.handlers]

        allows = sum(1 for d in decisions if d != PermissionDecision.DENY)
        denies = sum(1 for d in decisions if d == PermissionDecision.DENY)

        if self.require_all:
            # All must allow
            return PermissionDecision.DENY if denies > 0 else PermissionDecision.ALLOW
        else:
            # Any can allow
            return PermissionDecision.ALLOW if allows > 0 else PermissionDecision.DENY
