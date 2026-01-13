"""Tests for the REPL harness."""

import pytest

from agentself.harness.repl import REPLSubprocess, ExecutionResult, REPLState


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
