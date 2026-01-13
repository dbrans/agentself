"""Tests for the REPL harness."""

import json
import tempfile
from pathlib import Path

import pytest

from agentself.harness.repl import REPLSubprocess, ExecutionResult, REPLState
from agentself.harness.state import StateManager, SavedState, SavedFunction, SavedVariable, SavedCapability


class TestREPLSubprocess:
    """Tests for REPLSubprocess."""

    @pytest.fixture
    def repl(self):
        """Create a REPL subprocess for testing."""
        with REPLSubprocess() as r:
            yield r

    def test_execute_simple_statement(self, repl):
        """Test executing a simple statement."""
        result = repl.execute("x = 42")

        assert result.success
        assert result.error_type is None

    def test_execute_expression_returns_value(self, repl):
        """Test that expressions return their value."""
        repl.execute("x = 42")
        result = repl.execute("x + 1")

        assert result.success
        assert result.return_value == 43

    def test_execute_print_captures_stdout(self, repl):
        """Test that print output is captured."""
        result = repl.execute("print('Hello, World!')")

        assert result.success
        assert "Hello, World!" in result.stdout

    def test_execute_error_captures_info(self, repl):
        """Test that errors are properly captured."""
        result = repl.execute("1 / 0")

        assert not result.success
        assert result.error_type == "ZeroDivisionError"
        assert result.error_message is not None

    def test_execute_syntax_error(self, repl):
        """Test handling of syntax errors."""
        result = repl.execute("if True")

        assert not result.success
        assert result.error_type == "SyntaxError"

    def test_state_tracks_variables(self, repl):
        """Test that state tracks defined variables."""
        repl.execute("x = 42")
        repl.execute("y = 'hello'")
        state = repl.state()

        assert "x" in state.variables
        assert "y" in state.variables
        assert state.variables["x"] == "int"
        assert state.variables["y"] == "str"

    def test_state_tracks_functions(self, repl):
        """Test that state tracks defined functions."""
        repl.execute("def greet(name): return f'Hello, {name}!'")
        state = repl.state()

        assert len(state.defined_functions) == 1
        assert state.defined_functions[0]["name"] == "greet"
        assert "(name)" in state.defined_functions[0]["signature"]

    def test_state_tracks_history(self, repl):
        """Test that state tracks execution history."""
        repl.execute("x = 1")
        repl.execute("y = 2")
        repl.execute("z = x + y")
        state = repl.state()

        assert state.history_length == 3

    def test_persistence_across_executions(self, repl):
        """Test that state persists across execute calls."""
        repl.execute("counter = 0")
        repl.execute("counter += 1")
        repl.execute("counter += 1")
        result = repl.execute("counter")

        assert result.return_value == 2

    def test_function_definition_and_call(self, repl):
        """Test defining and calling functions."""
        repl.execute("""
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
""")
        result = repl.execute("factorial(5)")

        assert result.success
        assert result.return_value == 120

    def test_multiline_code(self, repl):
        """Test executing multi-line code."""
        result = repl.execute("""
data = [1, 2, 3, 4, 5]
total = sum(data)
average = total / len(data)
""")
        assert result.success

        result = repl.execute("average")
        assert result.return_value == 3.0

    def test_complex_return_values(self, repl):
        """Test that complex values are serialized."""
        result = repl.execute("{'a': 1, 'b': [1, 2, 3]}")

        assert result.success
        assert result.return_value == {"a": 1, "b": [1, 2, 3]}

    def test_inject_code(self, repl):
        """Test injecting code into namespace."""
        success = repl.inject("injected_var", "injected_var = 'I was injected'")

        assert success

        result = repl.execute("injected_var")
        assert result.return_value == "I was injected"


class TestRelayCapabilities:
    """Tests for relay capabilities (MCP-backed)."""

    @pytest.fixture
    def mock_relay_handler(self):
        """Create a mock relay handler for testing."""
        calls = []

        def handler(capability: str, method: str, kwargs: dict):
            calls.append((capability, method, kwargs))
            # Simulate different responses based on method
            if method == "echo":
                return kwargs.get("message", "")
            elif method == "add":
                return kwargs.get("a", 0) + kwargs.get("b", 0)
            elif method == "fail":
                raise RuntimeError("Simulated failure")
            elif method == "list_files":
                return ["file1.txt", "file2.txt"]
            else:
                return f"Called {capability}.{method}"

        handler.calls = calls
        return handler

    @pytest.fixture
    def repl_with_relay(self, mock_relay_handler):
        """Create a REPL with a mock relay handler."""
        with REPLSubprocess(relay_handler=mock_relay_handler) as r:
            yield r, mock_relay_handler

    def test_inject_relay_capability(self, repl_with_relay):
        """Test injecting a relay capability."""
        repl, handler = repl_with_relay

        tools = {
            "echo": {"description": "Echo a message"},
            "add": {"description": "Add two numbers"},
        }
        success = repl.inject_relay_capability("test", tools)
        assert success

        # Check it appears in state
        state = repl.state()
        assert "test" in state.capabilities

    def test_relay_capability_method_call(self, repl_with_relay):
        """Test calling a method on a relay capability."""
        repl, handler = repl_with_relay

        tools = {
            "echo": {"description": "Echo a message"},
            "add": {"description": "Add two numbers"},
        }
        repl.inject_relay_capability("math", tools)

        # Call a method
        result = repl.execute('math.add(a=3, b=4)')

        assert result.success
        assert result.return_value == 7
        assert len(handler.calls) == 1
        assert handler.calls[0] == ("math", "add", {"a": 3, "b": 4})

    def test_relay_capability_stores_result(self, repl_with_relay):
        """Test that relay results can be stored in variables."""
        repl, handler = repl_with_relay

        tools = {"list_files": {"description": "List files"}}
        repl.inject_relay_capability("fs", tools)

        repl.execute("files = fs.list_files()")
        result = repl.execute("files")

        assert result.success
        assert result.return_value == ["file1.txt", "file2.txt"]

    def test_relay_capability_error_handling(self, repl_with_relay):
        """Test that relay errors are properly propagated."""
        repl, handler = repl_with_relay

        tools = {"fail": {"description": "Always fails"}}
        repl.inject_relay_capability("bad", tools)

        result = repl.execute("bad.fail()")

        assert not result.success
        assert "Simulated failure" in result.error_message

    def test_relay_capability_unknown_method(self, repl_with_relay):
        """Test calling an unknown method on relay capability."""
        repl, handler = repl_with_relay

        tools = {"known": {"description": "A known method"}}
        repl.inject_relay_capability("cap", tools)

        result = repl.execute("cap.unknown()")

        assert not result.success
        assert "unknown" in result.error_message
        assert "known" in result.error_message  # Should list available methods

    def test_relay_capability_describe(self, repl_with_relay):
        """Test describe() on a relay capability."""
        repl, handler = repl_with_relay

        tools = {
            "read": {"description": "Read a file"},
            "write": {"description": "Write to a file"},
        }
        repl.inject_relay_capability("fs", tools)

        result = repl.execute("fs.describe()")

        assert result.success
        assert "fs" in result.return_value
        assert "read" in result.return_value
        assert "write" in result.return_value

    def test_multiple_relay_capabilities(self, repl_with_relay):
        """Test using multiple relay capabilities together."""
        repl, handler = repl_with_relay

        repl.inject_relay_capability("fs", {"list_files": {"description": "List"}})
        repl.inject_relay_capability("math", {"add": {"description": "Add"}})

        result = repl.execute("len(fs.list_files()) + math.add(a=1, b=2)")

        assert result.success
        assert result.return_value == 5  # 2 files + 3

    def test_relay_with_native_capability(self, repl_with_relay):
        """Test mixing relay and native capabilities."""
        repl, handler = repl_with_relay

        # Install relay capability
        repl.inject_relay_capability("remote", {"echo": {"description": "Echo"}})

        # Define native capability
        repl.execute("""
class LocalCap:
    name = "local"
    def greet(self, name):
        return f"Hello, {name}!"
    def describe(self):
        return "local: greet(name)"
local = LocalCap()
""")
        repl.register_capability("local")

        # Use both
        result = repl.execute('local.greet("World") + " " + remote.echo(message="Hi")')

        assert result.success
        assert result.return_value == "Hello, World! Hi"


class TestNativeCapabilities:
    """Tests for native capability registration."""

    @pytest.fixture
    def repl(self):
        """Create a REPL subprocess for testing."""
        with REPLSubprocess() as r:
            yield r

    def test_register_simple_capability(self, repl):
        """Test registering a simple capability."""
        # Define a capability class
        repl.execute("""
class MyCapability:
    name = "my_cap"
    description = "A test capability"

    def process(self, data):
        return len(data)

    def describe(self):
        return f"{self.name}: {self.description}"

my_cap = MyCapability()
""")

        # Register it
        cap_name = repl.register_capability("my_cap")
        assert cap_name == "my_cap"

        # Check it's listed
        caps = repl.list_capabilities()
        assert len(caps) == 1
        assert caps[0]["name"] == "my_cap"

    def test_register_invalid_object_fails(self, repl):
        """Test that registering invalid objects fails."""
        repl.execute("not_a_cap = 42")

        cap_name = repl.register_capability("not_a_cap")
        assert cap_name is None

    def test_register_nonexistent_fails(self, repl):
        """Test that registering nonexistent objects fails."""
        cap_name = repl.register_capability("does_not_exist")
        assert cap_name is None

    def test_use_registered_capability(self, repl):
        """Test using a registered capability."""
        repl.execute("""
class Counter:
    name = "counter"
    description = "A simple counter"

    def __init__(self):
        self.value = 0

    def increment(self):
        self.value += 1
        return self.value

    def describe(self):
        return "counter: increment() -> int"

counter = Counter()
""")

        repl.register_capability("counter")

        # Use the capability
        result = repl.execute("counter.increment()")
        assert result.return_value == 1

        result = repl.execute("counter.increment()")
        assert result.return_value == 2


class TestStateManager:
    """Tests for state persistence."""

    @pytest.fixture
    def temp_state_dir(self):
        """Create a temporary directory for state files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def state_manager(self, temp_state_dir):
        """Create a state manager with temp directory."""
        return StateManager(temp_state_dir)

    def test_save_and_load_state(self, state_manager):
        """Test basic save and load."""
        state = SavedState(
            functions=[SavedFunction(name="greet", source="def greet(x): return x", signature="(x)")],
            variables=[SavedVariable(name="x", var_type="json", value=42)],
        )

        path = state_manager.save(state, "test")
        assert path.exists()

        loaded = state_manager.load("test")
        assert loaded is not None
        assert len(loaded.functions) == 1
        assert loaded.functions[0].name == "greet"
        assert len(loaded.variables) == 1
        assert loaded.variables[0].value == 42

    def test_load_nonexistent(self, state_manager):
        """Test loading nonexistent state returns None."""
        assert state_manager.load("nonexistent") is None

    def test_list_states(self, state_manager):
        """Test listing saved states."""
        state_manager.save(SavedState(), "one")
        state_manager.save(SavedState(), "two")

        states = state_manager.list_states()
        assert "one" in states
        assert "two" in states

    def test_delete_state(self, state_manager):
        """Test deleting a state."""
        state_manager.save(SavedState(), "deleteme")
        assert "deleteme" in state_manager.list_states()

        assert state_manager.delete("deleteme")
        assert "deleteme" not in state_manager.list_states()
        assert not state_manager.delete("deleteme")  # Already deleted


class TestREPLStatePersistence:
    """Tests for REPL export/import functionality."""

    @pytest.fixture
    def repl(self):
        """Create a REPL subprocess for testing."""
        with REPLSubprocess() as r:
            yield r

    def test_export_empty_state(self, repl):
        """Test exporting empty state."""
        exported = repl.export_state()

        assert "functions" in exported
        assert "variables" in exported
        assert "history" in exported
        assert exported["functions"] == []
        assert exported["variables"] == []

    def test_export_with_variables(self, repl):
        """Test exporting variables."""
        repl.execute("x = 42")
        repl.execute("name = 'test'")
        repl.execute("data = [1, 2, 3]")

        exported = repl.export_state()

        var_names = {v["name"] for v in exported["variables"]}
        assert "x" in var_names
        assert "name" in var_names
        assert "data" in var_names

        # Check values
        vars_by_name = {v["name"]: v for v in exported["variables"]}
        assert vars_by_name["x"]["value"] == 42
        assert vars_by_name["x"]["type"] == "json"

    def test_export_with_function(self, repl):
        """Test exporting functions."""
        repl.execute("""
def greet(name):
    return f"Hello, {name}!"
""")

        exported = repl.export_state()

        assert len(exported["functions"]) == 1
        func = exported["functions"][0]
        assert func["name"] == "greet"
        assert "def greet" in func["source"]
        assert "(name)" in func["signature"]

    def test_export_history(self, repl):
        """Test that history is exported."""
        repl.execute("x = 1")
        repl.execute("y = 2")
        repl.execute("z = x + y")

        exported = repl.export_state()

        assert len(exported["history"]) == 3
        assert "x = 1" in exported["history"][0]

    def test_import_variables(self, repl):
        """Test importing variables."""
        import_data = {
            "functions": [],
            "variables": [
                {"name": "imported_x", "type": "json", "value": 100},
                {"name": "imported_list", "type": "json", "value": [1, 2, 3]},
            ],
            "native_capabilities": [],
            "history": [],
        }

        result = repl.import_state(import_data)

        assert result["variables_restored"] == 2
        assert result["variables_failed"] == []

        # Verify variables are accessible
        r = repl.execute("imported_x")
        assert r.return_value == 100

        r = repl.execute("imported_list")
        assert r.return_value == [1, 2, 3]

    def test_import_functions(self, repl):
        """Test importing functions."""
        import_data = {
            "functions": [
                {
                    "name": "double",
                    "source": "def double(x):\n    return x * 2",
                    "signature": "(x)",
                    "docstring": "",
                }
            ],
            "variables": [],
            "native_capabilities": [],
            "history": [],
        }

        result = repl.import_state(import_data)

        assert result["functions_restored"] == 1
        assert result["functions_failed"] == []

        # Verify function works
        r = repl.execute("double(21)")
        assert r.return_value == 42

    def test_import_restores_history(self, repl):
        """Test that import restores history."""
        import_data = {
            "functions": [],
            "variables": [],
            "native_capabilities": [],
            "history": ["x = 1", "y = 2"],
        }

        repl.import_state(import_data)
        state = repl.state()

        assert state.history_length == 2

    def test_roundtrip_state(self, repl):
        """Test full export/import roundtrip."""
        # Set up state
        repl.execute("counter = 5")
        repl.execute("""
def increment(x):
    return x + 1
""")
        repl.execute("result = increment(counter)")

        # Export
        exported = repl.export_state()

        # Create new REPL and import
        with REPLSubprocess() as repl2:
            result = repl2.import_state(exported)

            assert result["variables_restored"] >= 2  # counter and result
            assert result["functions_restored"] == 1

            # Verify state
            r = repl2.execute("counter")
            assert r.return_value == 5

            r = repl2.execute("increment(10)")
            assert r.return_value == 11
