"""Tests for core types and abstractions."""

import pytest
import time

from agentself.core import (
    CapabilityCall,
    CapabilityContract,
    ExecutionPlan,
    ExecutionResult,
    ExecutionMode,
    PermissionStrategy,
    DependencyInfo,
)


class TestCapabilityCall:
    """Tests for CapabilityCall."""

    def test_basic_creation(self):
        """Test creating a capability call."""
        call = CapabilityCall(
            capability_name="fs",
            method_name="read",
            args=("/path/to/file",),
            kwargs={},
        )

        assert call.capability_name == "fs"
        assert call.method_name == "read"
        assert call.args == ("/path/to/file",)

    def test_str_representation(self):
        """Test string representation."""
        call = CapabilityCall(
            capability_name="fs",
            method_name="write",
            args=("/path/to/file", "content"),
            kwargs={},
        )

        s = str(call)
        assert "fs.write" in s
        assert "/path/to/file" in s
        assert "content" in s

    def test_str_with_kwargs(self):
        """Test string representation with keyword arguments."""
        call = CapabilityCall(
            capability_name="cmd",
            method_name="run",
            args=("ls",),
            kwargs={"timeout": 30},
        )

        s = str(call)
        assert "cmd.run" in s
        assert "timeout=30" in s

    def test_matches_capability(self):
        """Test matching by capability name."""
        call = CapabilityCall(
            capability_name="fs",
            method_name="read",
            args=(),
            kwargs={},
        )

        assert call.matches(capability="fs")
        assert not call.matches(capability="cmd")

    def test_matches_method(self):
        """Test matching by method name."""
        call = CapabilityCall(
            capability_name="fs",
            method_name="read",
            args=(),
            kwargs={},
        )

        assert call.matches(method="read")
        assert not call.matches(method="write")

    def test_matches_both(self):
        """Test matching by both capability and method."""
        call = CapabilityCall(
            capability_name="fs",
            method_name="read",
            args=(),
            kwargs={},
        )

        assert call.matches(capability="fs", method="read")
        assert not call.matches(capability="fs", method="write")
        assert not call.matches(capability="cmd", method="read")

    def test_timestamp_auto_set(self):
        """Test that timestamp is automatically set."""
        before = time.time()
        call = CapabilityCall(
            capability_name="fs",
            method_name="read",
            args=(),
            kwargs={},
        )
        after = time.time()

        assert before <= call.timestamp <= after


class TestExecutionPlan:
    """Tests for ExecutionPlan."""

    def test_empty_plan(self):
        """Test an empty execution plan."""
        plan = ExecutionPlan(code="x = 1")

        assert plan.success
        assert plan.calls == []
        assert "no capability calls" in str(plan).lower()

    def test_plan_with_calls(self):
        """Test a plan with capability calls."""
        calls = [
            CapabilityCall("fs", "read", ("/file1",), {}),
            CapabilityCall("fs", "write", ("/file2", "content"), {}),
        ]
        plan = ExecutionPlan(code="...", calls=calls)

        assert plan.success
        assert len(plan.calls) == 2
        assert "fs.read" in str(plan)
        assert "fs.write" in str(plan)

    def test_failed_plan(self):
        """Test a failed plan."""
        plan = ExecutionPlan(
            code="invalid syntax here",
            success=False,
            error="SyntaxError: invalid syntax",
        )

        assert not plan.success
        assert "SyntaxError" in str(plan)

    def test_has_writes(self):
        """Test detecting write operations."""
        read_only = ExecutionPlan(
            code="...",
            calls=[CapabilityCall("fs", "read", (), {})],
        )
        assert not read_only.has_writes()

        with_write = ExecutionPlan(
            code="...",
            calls=[CapabilityCall("fs", "write", (), {})],
        )
        assert with_write.has_writes()

        with_run = ExecutionPlan(
            code="...",
            calls=[CapabilityCall("cmd", "run", (), {})],
        )
        assert with_run.has_writes()

    def test_capabilities_used(self):
        """Test getting set of capabilities used."""
        plan = ExecutionPlan(
            code="...",
            calls=[
                CapabilityCall("fs", "read", (), {}),
                CapabilityCall("fs", "write", (), {}),
                CapabilityCall("cmd", "run", (), {}),
            ],
        )

        used = plan.capabilities_used()
        assert used == {"fs", "cmd"}

    def test_variables_tracked(self):
        """Test variable tracking."""
        plan = ExecutionPlan(
            code="y = x + 1",
            variables_accessed={"x"},
            variables_defined={"y"},
        )

        assert "x" in plan.variables_accessed
        assert "y" in plan.variables_defined


class TestExecutionResult:
    """Tests for ExecutionResult."""

    def test_success_with_output(self):
        """Test successful result with output."""
        result = ExecutionResult(success=True, output="Hello\n", return_value=42)

        assert result.success
        assert "Hello" in str(result)
        assert "42" in str(result)

    def test_success_no_output(self):
        """Test successful result with no output."""
        result = ExecutionResult(success=True)

        assert result.success
        assert "no output" in str(result).lower()

    def test_failure_shows_error(self):
        """Test failed result shows error."""
        result = ExecutionResult(success=False, error="NameError: x is not defined")

        assert not result.success
        assert "NameError" in str(result)

    def test_permission_denied(self):
        """Test permission denied result."""
        result = ExecutionResult(
            success=False,
            error="Write access denied",
            permission_denied=True,
        )

        assert not result.success
        assert result.permission_denied
        assert "Permission denied" in str(result)

    def test_result_with_plan(self):
        """Test result includes plan."""
        plan = ExecutionPlan(code="x = 1")
        result = ExecutionResult(success=True, plan=plan)

        assert result.plan is plan


class TestDependencyInfo:
    """Tests for DependencyInfo."""

    def test_empty_dependencies(self):
        """Test empty dependency tracking."""
        deps = DependencyInfo()

        assert deps.variable_sources == {}
        assert deps.capability_users == {}

    def test_record_block(self):
        """Test recording a block's dependencies."""
        deps = DependencyInfo()
        plan = ExecutionPlan(
            code="y = fs.read('/file')",
            calls=[CapabilityCall("fs", "read", ("/file",), {})],
            variables_accessed=set(),
            variables_defined={"y"},
        )

        deps.record_block(0, plan)

        assert "y" in deps.variable_sources
        assert "fs" in deps.capability_users
        assert 0 in deps.capability_users["fs"]

    def test_get_affected_by_capability_change(self):
        """Test finding blocks affected by capability changes."""
        deps = DependencyInfo()

        # Block 0 uses fs
        plan0 = ExecutionPlan(
            code="x = fs.read('/file')",
            calls=[CapabilityCall("fs", "read", (), {})],
            variables_defined={"x"},
        )
        deps.record_block(0, plan0)

        # Block 1 uses cmd
        plan1 = ExecutionPlan(
            code="y = cmd.run('ls')",
            calls=[CapabilityCall("cmd", "run", (), {})],
            variables_defined={"y"},
        )
        deps.record_block(1, plan1)

        assert deps.get_affected_by_capability_change("fs") == [0]
        assert deps.get_affected_by_capability_change("cmd") == [1]
        assert deps.get_affected_by_capability_change("user") == []

    def test_get_variable_origin(self):
        """Test tracing where a variable came from."""
        deps = DependencyInfo()
        call = CapabilityCall("fs", "read", ("/file",), {})
        plan = ExecutionPlan(
            code="content = fs.read('/file')",
            calls=[call],
            variables_defined={"content"},
        )
        deps.record_block(0, plan)

        origin = deps.get_variable_origin("content")
        assert len(origin) == 1
        assert origin[0].capability_name == "fs"
        assert origin[0].method_name == "read"


class TestExecutionMode:
    """Tests for ExecutionMode enum."""

    def test_mode_values(self):
        """Test mode enum values."""
        assert ExecutionMode.RECORD.value == "record"
        assert ExecutionMode.EXECUTE.value == "execute"


class TestPermissionStrategy:
    """Tests for PermissionStrategy enum."""

    def test_strategy_values(self):
        """Test all strategy values exist."""
        assert PermissionStrategy.PRE_APPROVED.value == "pre_approved"
        assert PermissionStrategy.CONTRACT_BASED.value == "contract_based"
        assert PermissionStrategy.CALL_BY_CALL.value == "call_by_call"
        assert PermissionStrategy.BUDGET_BASED.value == "budget_based"
        assert PermissionStrategy.AUDIT_ONLY.value == "audit_only"


class TestCapabilityContract:
    """Tests for CapabilityContract."""

    def test_empty_contract(self):
        """Test empty contract has no effects declared."""
        contract = CapabilityContract()

        assert contract.reads == []
        assert contract.writes == []
        assert contract.executes == []
        assert contract.network == []
        assert contract.spawns is False
        assert "(no effects declared)" in str(contract)

    def test_contract_with_reads_writes(self):
        """Test contract with read/write patterns."""
        contract = CapabilityContract(
            reads=["file:*.py", "file:*.md"],
            writes=["file:src/**"],
        )

        assert len(contract.reads) == 2
        assert len(contract.writes) == 1
        assert "reads:" in str(contract)
        assert "writes:" in str(contract)

    def test_contract_covers_matching_resource(self):
        """Test covers() matches resources correctly."""
        contract = CapabilityContract(
            reads=["file:*.py"],
            writes=["file:src/*"],
        )

        # Should match
        assert contract.covers("reads", "file:main.py")
        assert contract.covers("writes", "file:src/app.py")

        # Should not match
        assert not contract.covers("reads", "file:data.json")
        assert not contract.covers("writes", "file:tests/test.py")

    def test_contract_merge(self):
        """Test merging two contracts."""
        c1 = CapabilityContract(
            reads=["file:*.py"],
            writes=["file:src/*"],
        )
        c2 = CapabilityContract(
            reads=["file:*.md"],
            network=["https://api.example.com/*"],
            spawns=True,
        )

        merged = c1.merge(c2)

        assert "file:*.py" in merged.reads
        assert "file:*.md" in merged.reads
        assert "file:src/*" in merged.writes
        assert "https://api.example.com/*" in merged.network
        assert merged.spawns is True

    def test_contract_is_subset_of(self):
        """Test subset checking."""
        parent = CapabilityContract(
            reads=["file:**"],
            writes=["file:src/**"],
            spawns=True,
        )
        child = CapabilityContract(
            reads=["file:src/main.py"],
            writes=["file:src/app.py"],
        )

        # Child should be subset of parent
        assert child.is_subset_of(parent)

        # Parent not subset of more restricted child
        # (This simplified check may not catch all cases)

    def test_contract_spawns_flag(self):
        """Test spawns flag in str representation."""
        contract = CapabilityContract(spawns=True)

        assert "spawns: true" in str(contract)

    def test_contract_all_fields(self):
        """Test contract with all fields populated."""
        contract = CapabilityContract(
            reads=["file:*.py"],
            writes=["file:output/*"],
            executes=["shell:git *"],
            network=["https://*"],
            spawns=True,
        )

        s = str(contract)
        assert "reads:" in s
        assert "writes:" in s
        assert "executes:" in s
        assert "network:" in s
        assert "spawns:" in s
