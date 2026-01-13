"""Tests for core types."""

import pytest

from agentself.core import (
    CapabilityContract,
    ExecutionResult,
)


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


class TestExecutionResult:
    """Tests for ExecutionResult."""

    def test_success_with_output(self):
        """Test successful result with output."""
        result = ExecutionResult(success=True, stdout="Hello\n", return_value=42)

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
        result = ExecutionResult(
            success=False,
            error_type="NameError",
            error_message="x is not defined",
        )

        assert not result.success
        assert "NameError" in str(result)
        assert "x is not defined" in str(result)

    def test_result_fields(self):
        """Test all result fields."""
        result = ExecutionResult(
            success=True,
            stdout="output",
            stderr="warning",
            return_value={"key": "value"},
            error_type=None,
            error_message=None,
        )

        assert result.stdout == "output"
        assert result.stderr == "warning"
        assert result.return_value == {"key": "value"}
