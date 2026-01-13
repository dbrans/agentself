"""Tests for the capabilities module."""

import tempfile
from pathlib import Path

import pytest

from agentself.capabilities.base import Capability
from agentself.capabilities.command_line import CommandLineCapability, CommandResult
from agentself.capabilities.file_system import FileSystemCapability


class TestCapabilityBase:
    """Tests for the Capability base class."""

    def test_describe_returns_name_and_description(self):
        """Test that describe() includes capability info."""
        cap = FileSystemCapability()
        desc = cap.describe()

        assert "fs" in desc  # Capability name
        assert "Read and write files" in desc

    def test_describe_lists_methods(self):
        """Test that describe() lists public methods."""
        cap = FileSystemCapability()
        desc = cap.describe()

        assert "read" in desc
        assert "write" in desc
        assert "list" in desc

    def test_repr_is_useful(self):
        """Test that repr shows useful info."""
        cap = FileSystemCapability()
        rep = repr(cap)

        assert "FileSystemCapability" in rep
        assert "fs" in rep  # Capability name

    def test_contract_returns_capability_contract(self):
        """Test that contract() returns a CapabilityContract."""
        from agentself.core import CapabilityContract

        cap = FileSystemCapability()
        contract = cap.contract()

        assert isinstance(contract, CapabilityContract)


class TestFileSystemCapability:
    """Tests for FileSystemCapability."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    def test_read_within_allowed_path(self, temp_dir):
        """Test reading a file within allowed paths."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")

        cap = FileSystemCapability(allowed_paths=[temp_dir])
        content = cap.read(str(test_file))

        assert content == "Hello, World!"

    def test_read_outside_allowed_path_raises(self, temp_dir):
        """Test that reading outside allowed paths raises PermissionError."""
        cap = FileSystemCapability(allowed_paths=[temp_dir])

        with pytest.raises(PermissionError) as exc:
            cap.read("/etc/passwd")

        assert "outside allowed paths" in str(exc.value)

    def test_write_when_not_read_only(self, temp_dir):
        """Test writing when capability is not read-only."""
        cap = FileSystemCapability(allowed_paths=[temp_dir], read_only=False)

        test_file = temp_dir / "output.txt"
        result = cap.write(str(test_file), "Test content")

        assert result is True
        assert test_file.read_text() == "Test content"

    def test_write_when_read_only_raises(self, temp_dir):
        """Test that writing when read-only raises PermissionError."""
        cap = FileSystemCapability(allowed_paths=[temp_dir], read_only=True)

        with pytest.raises(PermissionError) as exc:
            cap.write(str(temp_dir / "test.txt"), "content")

        assert "read-only" in str(exc.value)

    def test_list_files(self, temp_dir):
        """Test listing files matching a pattern."""
        (temp_dir / "file1.py").write_text("")
        (temp_dir / "file2.py").write_text("")
        (temp_dir / "file3.txt").write_text("")

        cap = FileSystemCapability(allowed_paths=[temp_dir])
        py_files = cap.list("*.py")

        assert len(py_files) == 2
        assert all(f.endswith(".py") for f in py_files)

    def test_exists_within_allowed(self, temp_dir):
        """Test checking if a file exists."""
        (temp_dir / "exists.txt").write_text("")

        cap = FileSystemCapability(allowed_paths=[temp_dir])

        assert cap.exists(str(temp_dir / "exists.txt")) is True
        assert cap.exists(str(temp_dir / "nope.txt")) is False

    def test_mkdir(self, temp_dir):
        """Test creating directories."""
        cap = FileSystemCapability(allowed_paths=[temp_dir])

        new_dir = temp_dir / "subdir" / "nested"
        result = cap.mkdir(str(new_dir))

        assert result is True
        assert new_dir.exists()

    def test_derive_read_only(self, temp_dir):
        """Test deriving a read-only version."""
        cap = FileSystemCapability(allowed_paths=[temp_dir], read_only=False)
        derived = cap.derive(read_only=True)

        assert derived.read_only is True
        assert cap.read_only is False  # Original unchanged

    def test_contract_reflects_config(self, temp_dir):
        """Test that contract reflects capability configuration."""
        cap = FileSystemCapability(allowed_paths=[temp_dir], read_only=True)
        contract = cap.contract()

        # Read-only should have reads but no writes
        assert len(contract.reads) > 0
        assert contract.writes == []


class TestCommandLineCapability:
    """Tests for CommandLineCapability."""

    def test_run_simple_command(self):
        """Test running a simple command."""
        cap = CommandLineCapability()
        result = cap.run("echo hello")

        assert result.exit_code == 0
        assert "hello" in result.stdout

    def test_run_with_allowlist(self):
        """Test running with command allowlist."""
        cap = CommandLineCapability(allowed_commands=["echo", "ls"])

        # Allowed command should work
        result = cap.run("echo test")
        assert result.exit_code == 0

    def test_run_blocked_command(self):
        """Test that blocked commands raise PermissionError."""
        cap = CommandLineCapability(allowed_commands=["echo"])

        with pytest.raises(PermissionError) as exc:
            cap.run("rm -rf /")

        assert "not allowed" in str(exc.value)

    def test_command_result_str(self):
        """Test CommandResult string representation."""
        result = CommandResult(exit_code=0, stdout="output", stderr="")
        s = str(result)

        assert "output" in s
        assert "exit code: 0" in s

    def test_derive_restricted_commands(self):
        """Test deriving with restricted commands."""
        cap = CommandLineCapability(allowed_commands=["echo", "ls", "cat"])
        derived = cap.derive(allowed_commands=["echo"])

        assert derived.allowed_commands == ["echo"]

    def test_run_interactive(self):
        """Test run_interactive returns simple string."""
        cap = CommandLineCapability()
        output = cap.run_interactive("echo hello")

        assert "hello" in output

    def test_timeout(self):
        """Test command timeout."""
        cap = CommandLineCapability(timeout=1)
        result = cap.run("sleep 10")

        assert result.exit_code == -1
        assert "timed out" in result.stderr

    def test_contract_reflects_allowlist(self):
        """Test that contract reflects command allowlist."""
        cap = CommandLineCapability(allowed_commands=["git", "npm"])
        contract = cap.contract()

        assert any("git" in e for e in contract.executes)
        assert any("npm" in e for e in contract.executes)

    def test_deny_shell_operators_allows_simple_command(self):
        """Test deny_shell_operators allows simple commands."""
        cap = CommandLineCapability(allowed_commands=["echo"], deny_shell_operators=True)
        result = cap.run("echo safe")

        assert result.exit_code == 0

    def test_deny_shell_operators_blocks_chaining(self):
        """Test deny_shell_operators blocks shell chaining."""
        cap = CommandLineCapability(allowed_commands=["echo"], deny_shell_operators=True)

        with pytest.raises(PermissionError) as exc:
            cap.run("echo safe && whoami")

        assert "Shell operators" in str(exc.value)

    def test_allowed_paths_blocks_absolute_path(self, tmp_path):
        """Test that absolute path args are blocked outside allowed_paths."""
        cap = CommandLineCapability(
            allowed_commands=["ls"],
            allowed_cwd=[tmp_path],
            allowed_paths=[tmp_path],
        )

        with pytest.raises(PermissionError) as exc:
            cap.run("ls /", cwd=str(tmp_path))

        assert "Path argument not allowed" in str(exc.value)

    def test_allowed_paths_blocks_parent_traversal(self, tmp_path):
        """Test that parent traversal is blocked."""
        cap = CommandLineCapability(
            allowed_commands=["ls"],
            allowed_cwd=[tmp_path],
            allowed_paths=[tmp_path],
        )

        with pytest.raises(PermissionError) as exc:
            cap.run("ls ../", cwd=str(tmp_path))

        assert "Path argument not allowed" in str(exc.value)

    def test_allowed_paths_allows_relative_inside(self, tmp_path):
        """Test that relative path args inside allowed_paths are allowed."""
        (tmp_path / "file.txt").write_text("ok")
        cap = CommandLineCapability(
            allowed_commands=["ls"],
            allowed_cwd=[tmp_path],
            allowed_paths=[tmp_path],
        )

        result = cap.run("ls file.txt", cwd=str(tmp_path))

        assert result.exit_code == 0

    def test_contract_includes_allowed_paths(self, tmp_path):
        """Test that contract reflects allowed_paths."""
        cap = CommandLineCapability(allowed_paths=[tmp_path])
        contract = cap.contract()

        assert any("file:" in entry for entry in contract.reads)
        assert any("file:" in entry for entry in contract.writes)
