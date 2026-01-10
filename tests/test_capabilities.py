"""Tests for the capabilities module."""

import tempfile
from pathlib import Path

import pytest

from agentself.capabilities.base import Capability
from agentself.capabilities.command_line import CommandLineCapability, CommandResult
from agentself.capabilities.file_system import FileSystemCapability
from agentself.capabilities.loader import CapabilityLoader, CapabilityManifest
from agentself.capabilities.self_source import SelfSourceCapability
from agentself.capabilities.user_communication import UserCommunicationCapability
from agentself.sandbox import Sandbox


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


class TestUserCommunicationCapability:
    """Tests for UserCommunicationCapability."""

    def test_say_queues_message(self):
        """Test that say() queues a message."""
        cap = UserCommunicationCapability()

        cap.say("Hello!")
        cap.say("World!")

        messages = cap.get_pending_messages()
        assert messages == ["Hello!", "World!"]

    def test_get_pending_messages_clears_queue(self):
        """Test that getting messages clears the queue."""
        cap = UserCommunicationCapability()

        cap.say("Test")
        cap.get_pending_messages()

        assert cap.get_pending_messages() == []

    def test_ask_with_preloaded_response(self):
        """Test asking with a pre-provided response."""
        cap = UserCommunicationCapability()
        cap.provide_response("What is your name?", "Alice")

        response = cap.ask("What is your name?")

        assert response == "Alice"

    def test_ask_without_response_returns_placeholder(self):
        """Test asking without a response returns placeholder."""
        cap = UserCommunicationCapability()

        response = cap.ask("Unknown question?")

        assert "Awaiting response" in response


class TestCommandLineCapability:
    """Tests for CommandLineCapability."""

    def test_run_allowed_command(self):
        """Test running an allowed command."""
        cap = CommandLineCapability(allowed_commands=["echo", "ls"])

        result = cap.run("echo 'Hello'")

        assert result.exit_code == 0
        assert "Hello" in result.stdout

    def test_run_disallowed_command_raises(self):
        """Test that running a disallowed command raises PermissionError."""
        cap = CommandLineCapability(allowed_commands=["echo"])

        with pytest.raises(PermissionError) as exc:
            cap.run("rm -rf /")

        assert "not allowed" in str(exc.value)

    def test_run_with_no_allowlist_allows_all(self):
        """Test that no allowlist allows all commands."""
        cap = CommandLineCapability(allowed_commands=None)

        result = cap.run("echo 'works'")

        assert result.exit_code == 0

    def test_command_result_str(self):
        """Test CommandResult string formatting."""
        result = CommandResult(exit_code=0, stdout="output", stderr="")

        assert "output" in str(result)
        assert "exit code: 0" in str(result)

    def test_run_interactive(self):
        """Test run_interactive returns combined output."""
        cap = CommandLineCapability()

        output = cap.run_interactive("echo 'test'")

        assert "test" in output


class TestSelfSourceCapabilityStaging:
    """Tests for SelfSourceCapability staging operations."""

    def test_add_capability_stages_new(self):
        """Test adding a new capability stages it."""
        cap = SelfSourceCapability()
        code = '''
class TestCapability(Capability):
    """A test capability."""
    name = "test"
    description = "Test."
'''
        result = cap.add_capability("test", code)

        assert "staged" in result.lower()
        assert "test" in cap._staged_capabilities

    def test_add_capability_validates_syntax(self):
        """Test that add_capability validates syntax."""
        cap = SelfSourceCapability()
        bad_code = "def foo( # syntax error"

        result = cap.add_capability("bad", bad_code)

        assert "syntax error" in result.lower()
        assert "bad" not in cap._staged_capabilities

    def test_add_capability_requires_capability_class(self):
        """Test that code must define a Capability subclass."""
        cap = SelfSourceCapability()
        code = "x = 1"  # Not a capability

        result = cap.add_capability("notcap", code)

        assert "must define a class" in result.lower()

    def test_staged_changes_shows_staged(self):
        """Test staged_changes shows staged capabilities."""
        cap = SelfSourceCapability()
        cap.add_capability("new_cap", """
class NewCap(Capability):
    name = "new"
    description = "New."
""")

        result = cap.staged_changes()

        assert "new_cap" in result
        assert "New Capabilities" in result

    def test_rollback_capability_discards_staged(self):
        """Test rollback_capability discards changes."""
        cap = SelfSourceCapability()
        cap.add_capability("temp", """
class Temp(Capability):
    name = "temp"
    description = "Temp."
""")

        assert "temp" in cap._staged_capabilities

        result = cap.rollback_capability("temp")

        assert "discarded" in result.lower()
        assert "temp" not in cap._staged_capabilities

    def test_rollback_all_clears_everything(self):
        """Test rollback_all clears all staged changes."""
        cap = SelfSourceCapability()
        cap.add_capability("one", """
class One(Capability):
    name = "one"
    description = "One."
""")
        cap.add_capability("two", """
class Two(Capability):
    name = "two"
    description = "Two."
""")

        assert len(cap._staged_capabilities) == 2

        result = cap.rollback_all()

        assert "2" in result
        assert len(cap._staged_capabilities) == 0

    def test_diff_capability_shows_changes(self):
        """Test diff_capability shows the diff."""
        cap = SelfSourceCapability()
        cap.add_capability("new", """
class NewCap(Capability):
    name = "new"
    description = "A new capability."
""")

        diff = cap.diff_capability("new")

        assert "NEW CAPABILITY" in diff
        assert "NewCap" in diff


class TestSelfSourceCapabilityTesting:
    """Tests for SelfSourceCapability test operations."""

    def test_test_capability_verifies_compilation(self):
        """Test that test_capability verifies compilation."""
        cap = SelfSourceCapability()
        cap.add_capability("testcap", """
class TestCap(Capability):
    name = "testcap"
    description = "Test capability."
""")

        result = cap.test_capability("testcap")

        assert "Compilation: OK" in result
        assert "Instantiation: OK" in result

    def test_test_capability_catches_instantiation_error(self):
        """Test that test_capability catches instantiation errors."""
        cap = SelfSourceCapability()
        cap.add_capability("badcap", """
class BadCap(Capability):
    name = "bad"
    description = "Bad."
    def __init__(self):
        raise ValueError("Cannot instantiate")
""")

        result = cap.test_capability("badcap")

        assert "Instantiation failed" in result


class TestSelfSourceCapabilityHotReload:
    """Tests for SelfSourceCapability hot-reload operations."""

    def test_reload_capability_injects_into_sandbox(self):
        """Test that reload_capability injects into sandbox."""
        sandbox = Sandbox()
        cap = SelfSourceCapability()
        cap._sandbox = sandbox

        cap.add_capability("dynamic", """
class DynamicCap(Capability):
    name = "dynamic"
    description = "Dynamically added."

    def greet(self) -> str:
        return "Hello from dynamic!"
""")

        result = cap.reload_capability("dynamic")

        assert "hot-reloaded" in result.lower()
        assert "dynamic" in sandbox.capabilities

        # Verify the capability works
        exec_result = sandbox.execute("dynamic.greet()")
        assert exec_result.success
        assert "Hello from dynamic" in exec_result.return_value

    def test_reload_capability_replaces_existing(self):
        """Test that reload replaces an existing capability."""
        # Start with a basic user capability
        user_cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": user_cap})
        cap = SelfSourceCapability()
        cap._sandbox = sandbox

        # Verify original works
        result = sandbox.execute("user.say('test')")
        assert result.success

        # Now replace it with a modified version
        cap.add_capability("user", """
class ModifiedUser(Capability):
    name = "user"
    description = "Modified user capability."

    def say(self, msg: str) -> str:
        return f"Modified: {msg}"
""")

        cap.reload_capability("user")

        # Verify new version works
        result = sandbox.execute("user.say('hello')")
        assert result.success
        assert "Modified: hello" in result.return_value

    def test_reload_without_sandbox_returns_error(self):
        """Test that reload without sandbox returns error."""
        cap = SelfSourceCapability()
        cap._sandbox = None

        cap.add_capability("test", """
class Test(Capability):
    name = "test"
    description = "Test."
""")

        result = cap.reload_capability("test")

        assert "sandbox not connected" in result.lower()


class TestSelfSourceCapabilityIntrospection:
    """Tests for SelfSourceCapability introspection operations."""

    def test_list_capabilities_shows_sandbox_caps(self):
        """Test that list_capabilities shows sandbox capabilities."""
        sandbox = Sandbox(capabilities={
            "fs": FileSystemCapability(),
            "user": UserCommunicationCapability(),
        })
        cap = SelfSourceCapability()
        cap._sandbox = sandbox

        caps = cap.list_capabilities()

        assert "fs" in caps
        assert "user" in caps

    def test_describe_capability_returns_description(self):
        """Test that describe_capability returns capability description."""
        user_cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": user_cap})
        cap = SelfSourceCapability()
        cap._sandbox = sandbox

        desc = cap.describe_capability("user")

        assert "user" in desc.lower()
        assert "say" in desc

    def test_read_capability_source_returns_source(self):
        """Test that read_capability_source returns source code."""
        user_cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": user_cap})
        cap = SelfSourceCapability()
        cap._sandbox = sandbox

        source = cap.read_capability_source("user")

        assert "class UserCommunicationCapability" in source
        assert "def say" in source

    def test_get_capability_config_returns_config(self):
        """Test that get_capability_config returns configuration."""
        fs_cap = FileSystemCapability(read_only=True)
        sandbox = Sandbox(capabilities={"fs": fs_cap})
        cap = SelfSourceCapability()
        cap._sandbox = sandbox

        config = cap.get_capability_config("fs")

        assert config.get("read_only") is True


class TestSelfSourceCapabilityDescribe:
    """Tests for SelfSourceCapability describe()."""

    def test_describe_shows_all_methods(self):
        """Test describe shows all the methods."""
        cap = SelfSourceCapability()
        desc = cap.describe()

        # Introspection
        assert "list_capabilities" in desc
        assert "describe_capability" in desc
        assert "read_capability_source" in desc

        # Staging
        assert "add_capability" in desc
        assert "modify_capability" in desc
        assert "diff_capability" in desc
        assert "staged_changes" in desc
        assert "rollback_capability" in desc

        # Testing
        assert "test_capability" in desc

        # Hot-reload
        assert "reload_capability" in desc

        # Persistence
        assert "commit_capability" in desc


class TestCapabilityLoader:
    """Tests for CapabilityLoader."""

    def test_list_available_shows_builtins(self):
        """Test that list_available shows built-in capabilities."""
        sandbox = Sandbox()
        loader = CapabilityLoader(sandbox=sandbox)

        available = loader.list_available()

        assert "fs" in available
        assert "cmd" in available
        assert "user" in available
        assert "self" in available

    def test_describe_available_returns_description(self):
        """Test describe_available returns capability info."""
        sandbox = Sandbox()
        loader = CapabilityLoader(sandbox=sandbox)

        desc = loader.describe_available("fs")

        assert "FileSystemCapability" in desc
        assert "Contract:" in desc

    def test_describe_available_unknown_returns_error(self):
        """Test describe_available handles unknown capability."""
        sandbox = Sandbox()
        loader = CapabilityLoader(sandbox=sandbox)

        desc = loader.describe_available("unknown")

        assert "Unknown capability" in desc

    def test_install_adds_capability_to_sandbox(self):
        """Test install adds capability to sandbox."""
        sandbox = Sandbox()
        loader = CapabilityLoader(sandbox=sandbox)
        sandbox.inject_capability("loader", loader)

        assert "fs" not in sandbox.capabilities

        result = loader.install("fs")

        assert "fs" in sandbox.capabilities
        assert isinstance(result, FileSystemCapability)

    def test_install_with_kwargs(self):
        """Test install passes kwargs to capability."""
        sandbox = Sandbox()
        loader = CapabilityLoader(sandbox=sandbox)
        sandbox.inject_capability("loader", loader)

        result = loader.install("fs", read_only=True)

        assert isinstance(result, FileSystemCapability)
        assert result.read_only is True

    def test_install_already_installed_returns_error(self):
        """Test installing already installed capability returns error."""
        sandbox = Sandbox(capabilities={"fs": FileSystemCapability()})
        loader = CapabilityLoader(sandbox=sandbox)

        result = loader.install("fs")

        assert "already installed" in str(result)

    def test_list_installed_shows_current_capabilities(self):
        """Test list_installed shows sandbox capabilities."""
        sandbox = Sandbox(capabilities={
            "fs": FileSystemCapability(),
            "user": UserCommunicationCapability(),
        })
        loader = CapabilityLoader(sandbox=sandbox)

        installed = loader.list_installed()

        assert "fs" in installed
        assert "user" in installed

    def test_uninstall_removes_capability(self):
        """Test uninstall removes capability from sandbox."""
        sandbox = Sandbox(capabilities={"fs": FileSystemCapability()})
        loader = CapabilityLoader(sandbox=sandbox)

        assert "fs" in sandbox.capabilities

        result = loader.uninstall("fs")

        assert "uninstalled" in result.lower()
        assert "fs" not in sandbox.capabilities

    def test_uninstall_loader_fails(self):
        """Test cannot uninstall the loader itself."""
        sandbox = Sandbox()
        loader = CapabilityLoader(sandbox=sandbox)
        sandbox.inject_capability("loader", loader)

        result = loader.uninstall("loader")

        assert "Cannot uninstall" in result
        assert "loader" in sandbox.capabilities

    def test_describe_installed_returns_capability_description(self):
        """Test describe_installed returns installed capability's description."""
        fs = FileSystemCapability(read_only=True)
        sandbox = Sandbox(capabilities={"fs": fs})
        loader = CapabilityLoader(sandbox=sandbox)

        desc = loader.describe_installed("fs")

        assert "fs" in desc
        assert "read" in desc.lower()

    def test_install_derived_creates_restricted_version(self):
        """Test install_derived creates a restricted capability."""
        sandbox = Sandbox(capabilities={"fs": FileSystemCapability()})
        loader = CapabilityLoader(sandbox=sandbox)

        result = loader.install_derived("fs_ro", "fs", read_only=True)

        assert "fs_ro" in sandbox.capabilities
        assert sandbox.capabilities["fs_ro"].read_only is True

    def test_get_contract_returns_contract(self):
        """Test get_contract returns capability's contract."""
        sandbox = Sandbox()
        loader = CapabilityLoader(sandbox=sandbox)

        contract = loader.get_contract("fs")

        assert contract is not None
        assert len(contract.reads) > 0

    def test_loader_contract_declares_spawns(self):
        """Test loader's own contract declares it spawns capabilities."""
        sandbox = Sandbox()
        loader = CapabilityLoader(sandbox=sandbox)

        contract = loader.contract()

        assert contract.spawns is True


class TestCapabilityContracts:
    """Tests for capability contract() implementations."""

    def test_file_system_contract_reflects_config(self):
        """Test FileSystemCapability contract reflects configuration."""
        # Read-write capability
        fs_rw = FileSystemCapability()
        contract = fs_rw.contract()
        assert len(contract.reads) > 0
        assert len(contract.writes) > 0

        # Read-only capability
        fs_ro = FileSystemCapability(read_only=True)
        contract = fs_ro.contract()
        assert len(contract.reads) > 0
        assert len(contract.writes) == 0

    def test_command_line_contract_reflects_allowlist(self):
        """Test CommandLineCapability contract reflects allowlist."""
        # Unrestricted
        cmd_all = CommandLineCapability()
        contract = cmd_all.contract()
        assert "shell:*" in contract.executes

        # Restricted
        cmd_git = CommandLineCapability(allowed_commands=["git", "ls"])
        contract = cmd_git.contract()
        assert "shell:git *" in contract.executes
        assert "shell:ls *" in contract.executes
        assert "shell:*" not in contract.executes

    def test_self_source_contract_declares_spawns(self):
        """Test SelfSourceCapability contract declares it can spawn."""
        cap = SelfSourceCapability()
        contract = cap.contract()

        assert contract.spawns is True

    def test_user_communication_contract(self):
        """Test UserCommunicationCapability has read/write contract."""
        cap = UserCommunicationCapability()
        contract = cap.contract()

        assert "user:input" in contract.reads
        assert "user:output" in contract.writes


class TestCapabilityDerive:
    """Tests for capability derive() functionality."""

    def test_file_system_derive_read_only(self):
        """Test deriving a read-only file system capability."""
        fs = FileSystemCapability(allowed_paths=["/tmp"])
        fs_ro = fs.derive(read_only=True)

        assert fs_ro.read_only is True
        assert fs.read_only is False  # Original unchanged

    def test_file_system_derive_restricts_paths(self):
        """Test deriving with more restricted paths."""
        fs = FileSystemCapability(allowed_paths=[Path("/tmp")])
        fs_sub = fs.derive(allowed_paths=[Path("/tmp/subdir")])

        # Derived should have the restricted path
        assert any("subdir" in str(p) for p in fs_sub.allowed_paths)

    def test_command_line_derive_restricts_commands(self):
        """Test deriving with fewer allowed commands."""
        cmd = CommandLineCapability(allowed_commands=["git", "ls", "cat"])
        cmd_git = cmd.derive(allowed_commands=["git"])

        assert cmd_git.allowed_commands == ["git"]

    def test_derive_returns_new_instance(self):
        """Test that derive returns a new instance, not modifying original."""
        fs = FileSystemCapability()
        fs_ro = fs.derive(read_only=True)

        assert fs is not fs_ro
        assert fs.read_only is False
        assert fs_ro.read_only is True
