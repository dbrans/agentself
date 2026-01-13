"""Tests for the permission handling system."""

import pytest
from unittest.mock import patch

from agentself.core import CapabilityCall, ExecutionPlan
from agentself.permissions import (
    PermissionDecision,
    PermissionRequest,
    PermissionRule,
    AutoApproveHandler,
    AutoDenyHandler,
    PolicyHandler,
    CompositeHandler,
)


def make_request(*calls) -> PermissionRequest:
    """Helper to create a permission request with calls."""
    plan = ExecutionPlan(
        code="...",
        calls=list(calls),
    )
    return PermissionRequest(plan=plan)


def make_call(cap: str, method: str) -> CapabilityCall:
    """Helper to create a capability call."""
    return CapabilityCall(
        capability_name=cap,
        method_name=method,
        args=(),
        kwargs={},
    )


class TestPermissionRequest:
    """Tests for PermissionRequest."""

    def test_summary_no_calls(self):
        """Test summary with no calls."""
        plan = ExecutionPlan(code="x = 1")
        request = PermissionRequest(plan=plan)

        summary = request.summary()
        assert "no capability calls" in summary.lower()

    def test_summary_with_calls(self):
        """Test summary with calls."""
        request = make_request(
            make_call("fs", "read"),
            make_call("fs", "write"),
        )

        summary = request.summary()
        assert "fs.read" in summary
        assert "fs.write" in summary
        assert "2" in summary  # number of calls


class TestAutoApproveHandler:
    """Tests for AutoApproveHandler."""

    def test_always_allows(self):
        """Test that it always allows."""
        handler = AutoApproveHandler()
        request = make_request(make_call("fs", "write"))

        decision = handler.check(request)

        assert decision == PermissionDecision.ALLOW

    def test_allows_empty_request(self):
        """Test that empty requests are allowed."""
        handler = AutoApproveHandler()
        request = make_request()

        decision = handler.check(request)

        assert decision == PermissionDecision.ALLOW


class TestAutoDenyHandler:
    """Tests for AutoDenyHandler."""

    def test_always_denies(self):
        """Test that it always denies."""
        handler = AutoDenyHandler()
        request = make_request(make_call("fs", "read"))

        decision = handler.check(request)

        assert decision == PermissionDecision.DENY


class TestPermissionRule:
    """Tests for PermissionRule."""

    def test_match_any(self):
        """Test rule that matches any call."""
        rule = PermissionRule()
        call = make_call("fs", "read")

        assert rule.matches(call)

    def test_match_capability(self):
        """Test matching by capability."""
        rule = PermissionRule(capability="fs")

        assert rule.matches(make_call("fs", "read"))
        assert rule.matches(make_call("fs", "write"))
        assert not rule.matches(make_call("cmd", "run"))

    def test_match_method(self):
        """Test matching by method."""
        rule = PermissionRule(method="read")

        assert rule.matches(make_call("fs", "read"))
        assert rule.matches(make_call("db", "read"))
        assert not rule.matches(make_call("fs", "write"))

    def test_match_both(self):
        """Test matching by both capability and method."""
        rule = PermissionRule(capability="fs", method="read")

        assert rule.matches(make_call("fs", "read"))
        assert not rule.matches(make_call("fs", "write"))
        assert not rule.matches(make_call("cmd", "read"))

    def test_arg_validator(self):
        """Test custom argument validation."""

        def only_safe_paths(args, kwargs):
            if args:
                return str(args[0]).startswith("/safe/")
            return False

        rule = PermissionRule(
            capability="fs",
            method="read",
            arg_validator=only_safe_paths,
        )

        safe_call = CapabilityCall("fs", "read", ("/safe/file.txt",), {})
        unsafe_call = CapabilityCall("fs", "read", ("/etc/passwd",), {})

        assert rule.matches(safe_call)
        assert not rule.matches(unsafe_call)


class TestPolicyHandler:
    """Tests for PolicyHandler."""

    def test_default_deny(self):
        """Test default deny behavior."""
        handler = PolicyHandler(default=PermissionDecision.DENY)
        request = make_request(make_call("fs", "read"))

        decision = handler.check(request)

        assert decision == PermissionDecision.DENY

    def test_default_allow(self):
        """Test default allow behavior."""
        handler = PolicyHandler(default=PermissionDecision.ALLOW)
        request = make_request(make_call("fs", "read"))

        decision = handler.check(request)

        assert decision == PermissionDecision.ALLOW

    def test_allow_rule(self):
        """Test allowing with a rule."""
        handler = PolicyHandler(default=PermissionDecision.DENY)
        handler.allow("fs", "read")

        request = make_request(make_call("fs", "read"))
        assert handler.check(request) == PermissionDecision.ALLOW

        request = make_request(make_call("fs", "write"))
        assert handler.check(request) == PermissionDecision.DENY

    def test_deny_rule(self):
        """Test denying with a rule."""
        handler = PolicyHandler(default=PermissionDecision.ALLOW)
        handler.deny("cmd")  # Deny all cmd operations

        request = make_request(make_call("fs", "read"))
        assert handler.check(request) == PermissionDecision.ALLOW

        request = make_request(make_call("cmd", "run"))
        assert handler.check(request) == PermissionDecision.DENY

    def test_first_matching_rule_wins(self):
        """Test that first matching rule wins."""
        handler = PolicyHandler()
        handler.allow("fs", "read")
        handler.deny("fs")  # This comes after, shouldn't affect read

        request = make_request(make_call("fs", "read"))
        assert handler.check(request) == PermissionDecision.ALLOW

    def test_any_deny_denies_all(self):
        """Test that any denied call denies the whole request."""
        handler = PolicyHandler()
        handler.allow("fs", "read")
        handler.deny("cmd")

        request = make_request(
            make_call("fs", "read"),  # Allowed
            make_call("cmd", "run"),  # Denied
        )

        assert handler.check(request) == PermissionDecision.DENY

    def test_all_allowed_allows(self):
        """Test that all calls must be allowed."""
        handler = PolicyHandler()
        handler.allow("fs")
        handler.allow("user")

        request = make_request(
            make_call("fs", "read"),
            make_call("user", "say"),
        )

        assert handler.check(request) == PermissionDecision.ALLOW

    def test_empty_request_allowed(self):
        """Test that empty requests are allowed."""
        handler = PolicyHandler(default=PermissionDecision.DENY)
        request = make_request()

        assert handler.check(request) == PermissionDecision.ALLOW

    def test_fluent_api(self):
        """Test fluent API for building policies."""
        handler = (
            PolicyHandler()
            .allow("fs", "read")
            .allow("fs", "list")
            .deny("cmd")
        )

        assert handler.check(make_request(make_call("fs", "read"))) == PermissionDecision.ALLOW
        assert handler.check(make_request(make_call("cmd", "run"))) == PermissionDecision.DENY


class TestCompositeHandler:
    """Tests for CompositeHandler."""

    def test_require_all(self):
        """Test that all handlers must allow."""
        handler = CompositeHandler(
            handlers=[
                AutoApproveHandler(),
                AutoDenyHandler(),
            ],
            require_all=True,
        )

        request = make_request(make_call("fs", "read"))

        # One denies, so overall is denied
        assert handler.check(request) == PermissionDecision.DENY

    def test_require_any(self):
        """Test that any handler can allow."""
        handler = CompositeHandler(
            handlers=[
                AutoApproveHandler(),
                AutoDenyHandler(),
            ],
            require_all=False,
        )

        request = make_request(make_call("fs", "read"))

        # One allows, so overall is allowed
        assert handler.check(request) == PermissionDecision.ALLOW

    def test_all_allow(self):
        """Test when all handlers allow."""
        handler = CompositeHandler(
            handlers=[
                AutoApproveHandler(),
                AutoApproveHandler(),
            ],
            require_all=True,
        )

        request = make_request(make_call("fs", "read"))

        assert handler.check(request) == PermissionDecision.ALLOW

    def test_all_deny(self):
        """Test when all handlers deny."""
        handler = CompositeHandler(
            handlers=[
                AutoDenyHandler(),
                AutoDenyHandler(),
            ],
            require_all=False,
        )

        request = make_request(make_call("fs", "read"))

        assert handler.check(request) == PermissionDecision.DENY
