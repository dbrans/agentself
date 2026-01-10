"""Tests for the sandbox module with two-phase execution."""

import pytest

from agentself.sandbox import Sandbox, SAFE_BUILTINS
from agentself.core import ExecutionResult, ExecutionPlan
from agentself.capabilities.file_system import FileSystemCapability
from agentself.capabilities.user_communication import UserCommunicationCapability
from agentself.permissions import (
    AutoApproveHandler,
    AutoDenyHandler,
    PolicyHandler,
    PermissionDecision,
)


class TestExecutionResult:
    """Tests for ExecutionResult."""

    def test_success_with_output(self):
        """Test successful result with output."""
        result = ExecutionResult(success=True, output="Hello\n", return_value=42)

        assert result.success
        assert "Hello" in str(result)
        assert "42" in str(result)

    def test_failure_shows_error(self):
        """Test failed result shows error."""
        result = ExecutionResult(success=False, error="NameError: x is not defined")

        assert not result.success
        assert "NameError" in str(result)

    def test_permission_denied_shows_in_str(self):
        """Test permission denied result."""
        result = ExecutionResult(
            success=False,
            permission_denied=True,
            error="fs.write denied",
        )

        assert "Permission denied" in str(result)


class TestSandboxBasicExecution:
    """Tests for basic sandbox execution."""

    def test_basic_execution(self):
        """Test basic code execution."""
        sandbox = Sandbox()

        result = sandbox.execute("1 + 1")

        assert result.success
        assert result.return_value == 2

    def test_print_captured(self):
        """Test that print output is captured."""
        sandbox = Sandbox()

        result = sandbox.execute("print('Hello, World!')")

        assert result.success
        assert "Hello, World!" in result.output

    def test_variable_persistence(self):
        """Test that variables persist across executions."""
        sandbox = Sandbox()

        sandbox.execute("x = 42")
        result = sandbox.execute("x * 2")

        assert result.return_value == 84

    def test_function_definition(self):
        """Test defining and calling functions."""
        sandbox = Sandbox()

        sandbox.execute("def double(n): return n * 2")
        result = sandbox.execute("double(21)")

        assert result.return_value == 42

    def test_import_blocked(self):
        """Test that import is blocked."""
        sandbox = Sandbox()

        result = sandbox.execute("import os")

        assert not result.success
        assert "import" in result.error.lower() or "name" in result.error.lower()

    def test_open_blocked(self):
        """Test that open() is blocked."""
        sandbox = Sandbox()

        result = sandbox.execute("open('/etc/passwd')")

        assert not result.success
        assert "open" in result.error.lower() or "name" in result.error.lower()

    def test_safe_builtins_available(self):
        """Test that safe builtins work."""
        sandbox = Sandbox()

        # len
        result = sandbox.execute("len([1, 2, 3])")
        assert result.return_value == 3

        # range
        result = sandbox.execute("list(range(5))")
        assert result.return_value == [0, 1, 2, 3, 4]

        # sorted
        result = sandbox.execute("sorted([3, 1, 2])")
        assert result.return_value == [1, 2, 3]


class TestSandboxCapabilities:
    """Tests for capability handling in sandbox."""

    def test_capability_injection(self):
        """Test that capabilities are accessible in sandbox."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": cap})

        result = sandbox.execute("user.say('test')")

        assert result.success
        assert cap.get_pending_messages() == ["test"]

    def test_capability_describe_works(self):
        """Test that capability describe() works in sandbox."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": cap})

        result = sandbox.execute("user.describe()")

        assert result.success
        assert "user" in result.return_value.lower()

    def test_caps_dict_available(self):
        """Test that caps dict is available for discovery."""
        cap1 = UserCommunicationCapability()
        cap2 = FileSystemCapability()
        sandbox = Sandbox(capabilities={"user": cap1, "fs": cap2})

        result = sandbox.execute("list(caps.keys())")

        assert result.success
        assert "user" in result.return_value
        assert "fs" in result.return_value

    def test_inject_capability_at_runtime(self):
        """Test adding capability after creation."""
        sandbox = Sandbox()
        cap = UserCommunicationCapability()

        sandbox.inject_capability("user", cap)
        result = sandbox.execute("user.say('hello')")

        assert result.success

    def test_remove_capability(self):
        """Test removing a capability."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": cap})

        sandbox.remove_capability("user")
        result = sandbox.execute("user")

        assert not result.success


class TestSandboxTwoPhaseExecution:
    """Tests for two-phase execution (analyze then execute)."""

    def test_analyze_records_calls(self):
        """Test that analyze records capability calls."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": cap})

        plan = sandbox.analyze("user.say('test')")

        assert plan.success
        assert len(plan.calls) == 1
        assert plan.calls[0].capability_name == "user"
        assert plan.calls[0].method_name == "say"

    def test_analyze_doesnt_execute(self):
        """Test that analyze doesn't actually execute."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": cap})

        sandbox.analyze("user.say('should not appear')")

        # The message should NOT be in pending messages
        assert cap.get_pending_messages() == []

    def test_analyze_records_multiple_calls(self):
        """Test analyzing code with multiple capability calls."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": cap})

        plan = sandbox.analyze("""
user.say('first')
user.say('second')
user.say('third')
""")

        assert plan.success
        assert len(plan.calls) == 3

    def test_analyze_tracks_variables(self):
        """Test that analyze tracks variable usage."""
        sandbox = Sandbox()

        plan = sandbox.analyze("y = x + 1")

        assert "x" in plan.variables_accessed
        assert "y" in plan.variables_defined

    def test_execute_includes_plan(self):
        """Test that execute result includes the plan."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": cap})

        result = sandbox.execute("user.say('test')")

        assert result.plan is not None
        assert len(result.plan.calls) == 1

    def test_execute_records_actual_calls(self):
        """Test that execute records actual calls made."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": cap})

        result = sandbox.execute("user.say('test')")

        assert len(result.calls) == 1
        assert result.calls[0].method_name == "say"


class TestSandboxPermissions:
    """Tests for permission handling in sandbox."""

    def test_auto_approve_allows(self):
        """Test that AutoApproveHandler allows execution."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(
            capabilities={"user": cap},
            permission_handler=AutoApproveHandler(),
        )

        result = sandbox.execute("user.say('test')")

        assert result.success
        assert not result.permission_denied

    def test_auto_deny_blocks(self):
        """Test that AutoDenyHandler blocks execution."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(
            capabilities={"user": cap},
            permission_handler=AutoDenyHandler(),
        )

        result = sandbox.execute("user.say('test')")

        assert not result.success
        assert result.permission_denied

    def test_policy_allows_matching(self):
        """Test that PolicyHandler allows matching calls."""
        cap = UserCommunicationCapability()
        handler = PolicyHandler().allow("user")
        sandbox = Sandbox(
            capabilities={"user": cap},
            permission_handler=handler,
        )

        result = sandbox.execute("user.say('test')")

        assert result.success

    def test_policy_denies_non_matching(self):
        """Test that PolicyHandler denies non-matching calls."""
        cap = UserCommunicationCapability()
        handler = PolicyHandler().allow("fs")  # Only allow fs, not user
        sandbox = Sandbox(
            capabilities={"user": cap},
            permission_handler=handler,
        )

        result = sandbox.execute("user.say('test')")

        assert not result.success
        assert result.permission_denied

    def test_skip_permission_flag(self):
        """Test skip_permission flag bypasses checking."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(
            capabilities={"user": cap},
            permission_handler=AutoDenyHandler(),  # Would normally deny
        )

        result = sandbox.execute("user.say('test')", skip_permission=True)

        assert result.success

    def test_execute_unchecked(self):
        """Test execute_unchecked bypasses permission."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(
            capabilities={"user": cap},
            permission_handler=AutoDenyHandler(),
        )

        result = sandbox.execute_unchecked("user.say('test')")

        assert result.success

    def test_no_permission_needed_without_calls(self):
        """Test that code without capability calls doesn't need permission."""
        sandbox = Sandbox(permission_handler=AutoDenyHandler())

        result = sandbox.execute("1 + 1")

        assert result.success  # Pure computation doesn't need permission


class TestSandboxStateManagement:
    """Tests for sandbox state management."""

    def test_get_variable(self):
        """Test getting variables from sandbox."""
        sandbox = Sandbox()
        sandbox.execute("x = 42")

        assert sandbox.get_variable("x") == 42

    def test_set_variable(self):
        """Test setting variables in sandbox."""
        sandbox = Sandbox()
        sandbox.set_variable("x", 100)

        result = sandbox.execute("x + 1")

        assert result.return_value == 101

    def test_reset_clears_variables(self):
        """Test that reset clears variables but keeps capabilities."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": cap})
        sandbox.execute("x = 42")

        sandbox.reset()

        # Variable should be gone
        result = sandbox.execute("x")
        assert not result.success

        # Capability should remain
        result = sandbox.execute("user.say('test')")
        assert result.success

    def test_reset_clears_history(self):
        """Test that reset clears execution history."""
        sandbox = Sandbox()
        sandbox.execute("x = 1")
        sandbox.execute("y = 2")

        sandbox.reset()

        assert sandbox.get_history() == []

    def test_get_history(self):
        """Test getting execution history."""
        sandbox = Sandbox()

        sandbox.execute("x = 1")
        sandbox.execute("y = 2")

        history = sandbox.get_history()
        assert len(history) == 2
        assert all(r.success for r in history)

    def test_get_dependencies(self):
        """Test getting dependency info."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": cap})

        sandbox.execute("user.say('test')")

        deps = sandbox.get_dependencies()
        assert "user" in deps.capability_users
        assert 0 in deps.capability_users["user"]


class TestSandboxDescribe:
    """Tests for sandbox describe()."""

    def test_describe_shows_capabilities(self):
        """Test that describe shows capabilities."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": cap})

        desc = sandbox.describe()

        assert "Capabilities" in desc
        assert "user" in desc

    def test_describe_shows_variables(self):
        """Test that describe shows variables."""
        sandbox = Sandbox()
        sandbox.execute("x = 42")

        desc = sandbox.describe()

        assert "Variables" in desc
        assert "x" in desc

    def test_describe_shows_history_count(self):
        """Test that describe shows execution history count."""
        sandbox = Sandbox()
        sandbox.execute("x = 1")
        sandbox.execute("y = 2")

        desc = sandbox.describe()

        assert "2 block" in desc


class TestSafeBuiltins:
    """Tests for safe builtins."""

    def test_safe_builtins_includes_types(self):
        """Test that safe builtins include basic types."""
        assert "int" in SAFE_BUILTINS
        assert "str" in SAFE_BUILTINS
        assert "list" in SAFE_BUILTINS
        assert "dict" in SAFE_BUILTINS

    def test_safe_builtins_includes_functions(self):
        """Test that safe builtins include common functions."""
        assert "len" in SAFE_BUILTINS
        assert "range" in SAFE_BUILTINS
        assert "sorted" in SAFE_BUILTINS
        assert "print" in SAFE_BUILTINS

    def test_safe_builtins_excludes_dangerous(self):
        """Test that safe builtins exclude dangerous functions."""
        assert "open" not in SAFE_BUILTINS
        assert "exec" not in SAFE_BUILTINS
        assert "eval" not in SAFE_BUILTINS
        assert "__import__" not in SAFE_BUILTINS
        assert "compile" not in SAFE_BUILTINS
