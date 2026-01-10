"""Tests for the sandbox module."""

import pytest

from agentself.sandbox import Sandbox, ExecutionResult
from agentself.capabilities.file_system import FileSystemCapability
from agentself.capabilities.user_communication import UserCommunicationCapability


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


class TestSandbox:
    """Tests for the Sandbox class."""
    
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
    
    def test_execute_multi(self):
        """Test executing multiple statements."""
        sandbox = Sandbox()
        
        results = sandbox.execute_multi([
            "x = 1",
            "y = 2",
            "x + y",
        ])
        
        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[2].return_value == 3
    
    def test_execute_multi_stops_on_error(self):
        """Test that execute_multi stops on first error."""
        sandbox = Sandbox()
        
        results = sandbox.execute_multi([
            "x = 1",
            "y = undefined",  # Error
            "z = 3",  # Should not run
        ])
        
        assert len(results) == 2
        assert results[0].success
        assert not results[1].success
    
    def test_describe(self):
        """Test sandbox describe()."""
        cap = UserCommunicationCapability()
        sandbox = Sandbox(capabilities={"user": cap})
        sandbox.execute("x = 42")
        
        desc = sandbox.describe()
        
        assert "Capabilities" in desc
        assert "user" in desc
        assert "Variables" in desc
        assert "x" in desc
