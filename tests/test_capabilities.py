"""Tests for the capabilities module."""

import tempfile
from pathlib import Path

import pytest

from agentself.capabilities.base import Capability
from agentself.capabilities.file_system import FileSystemCapability
from agentself.capabilities.user_communication import UserCommunicationCapability
from agentself.capabilities.command_line import CommandLineCapability, CommandResult


class TestCapabilityBase:
    """Tests for the Capability base class."""
    
    def test_describe_returns_name_and_description(self):
        """Test that describe() includes capability info."""
        cap = FileSystemCapability()
        desc = cap.describe()
        
        assert "file_system" in desc
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
        assert "file_system" in rep


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


class TestSelfSourceCapability:
    """Tests for SelfSourceCapability."""
    
    def test_add_capability_stages_new(self):
        """Test adding a new capability stages it."""
        from agentself.capabilities.self_source import SelfSourceCapability
        
        cap = SelfSourceCapability()
        code = '''
from agentself.capabilities.base import Capability

class TestCapability(Capability):
    """A test capability."""
    name = "test"
    description = "Test."
'''
        result = cap.add_capability("test", code)
        
        assert "staged" in result.lower()
        assert "test" in cap._staged_capabilities
    
    def test_track_changes_shows_staged(self):
        """Test track_changes shows staged capabilities."""
        from agentself.capabilities.self_source import SelfSourceCapability
        
        cap = SelfSourceCapability()
        cap.add_capability("new_cap", """
from agentself.capabilities.base import Capability
class NewCap(Capability):
    name = "new"
""")
        
        result = cap.track_changes()
        
        assert "new_cap" in result
        assert "New Capabilities" in result
    
    def test_rollback_capability_discards_staged(self):
        """Test rollback_capability discards changes."""
        from agentself.capabilities.self_source import SelfSourceCapability
        
        cap = SelfSourceCapability()
        cap.add_capability("temp", """
from agentself.capabilities.base import Capability
class Temp(Capability):
    name = "temp"
""")
        
        assert "temp" in cap._staged_capabilities
        
        result = cap.rollback_capability("temp")
        
        assert "discarded" in result.lower()
        assert "temp" not in cap._staged_capabilities
    
    def test_rollback_all_clears_everything(self):
        """Test rollback_all clears all staged changes."""
        from agentself.capabilities.self_source import SelfSourceCapability
        
        cap = SelfSourceCapability()
        cap.add_capability("one", """
from agentself.capabilities.base import Capability
class One(Capability):
    name = "one"
""")
        cap.add_capability("two", """
from agentself.capabilities.base import Capability
class Two(Capability):
    name = "two"
""")
        
        assert len(cap._staged_capabilities) == 2
        
        result = cap.rollback_all()
        
        assert "2" in result
        assert len(cap._staged_capabilities) == 0
    
    def test_describe_shows_new_methods(self):
        """Test describe shows the new modification methods."""
        from agentself.capabilities.self_source import SelfSourceCapability
        
        cap = SelfSourceCapability()
        desc = cap.describe()
        
        assert "modify_capability" in desc
        assert "diff_capability" in desc
        assert "track_changes" in desc
        assert "rollback" in desc

