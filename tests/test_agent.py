"""Tests for the Agent class."""

from unittest.mock import MagicMock, patch

import pytest

from agentself.agent import (
    Agent,
    Message,
    ToolSpec,
    _generate_tool_spec,
    _python_type_to_json_schema,
    tool,
)


class TestPythonTypeToJsonSchema:
    """Tests for type conversion."""

    def test_str_type(self):
        assert _python_type_to_json_schema(str) == {"type": "string"}

    def test_int_type(self):
        assert _python_type_to_json_schema(int) == {"type": "integer"}

    def test_float_type(self):
        assert _python_type_to_json_schema(float) == {"type": "number"}

    def test_bool_type(self):
        assert _python_type_to_json_schema(bool) == {"type": "boolean"}

    def test_list_type(self):
        assert _python_type_to_json_schema(list) == {"type": "array"}

    def test_dict_type(self):
        assert _python_type_to_json_schema(dict) == {"type": "object"}


class TestToolDecorator:
    """Tests for the @tool decorator."""

    def test_marks_function_as_tool(self):
        @tool
        def my_tool():
            pass

        assert hasattr(my_tool, "_is_tool")
        assert my_tool._is_tool is True

    def test_preserves_function(self):
        @tool
        def my_tool():
            """Test docstring."""
            return "result"

        assert my_tool() == "result"
        assert my_tool.__doc__ == "Test docstring."


class TestGenerateToolSpec:
    """Tests for tool spec generation."""

    def test_generates_spec_from_function(self):
        def greet(name: str) -> str:
            """Say hello to someone."""
            return f"Hello, {name}!"

        spec = _generate_tool_spec(greet)

        assert spec.name == "greet"
        assert spec.description == "Say hello to someone."
        assert "name" in spec.parameters["properties"]
        assert spec.parameters["properties"]["name"]["type"] == "string"
        assert "name" in spec.parameters["required"]

    def test_optional_parameter(self):
        def greet(name: str, formal: bool = False) -> str:
            """Say hello."""
            return f"Hello, {name}"

        spec = _generate_tool_spec(greet)

        assert "name" in spec.parameters["required"]
        assert "formal" not in spec.parameters["required"]


class TestMessage:
    """Tests for Message class."""

    def test_to_api_format(self):
        msg = Message(role="user", content="Hello")
        assert msg.to_api() == {"role": "user", "content": "Hello"}

    def test_with_list_content(self):
        content = [{"type": "text", "text": "Hello"}]
        msg = Message(role="assistant", content=content)
        assert msg.to_api() == {"role": "assistant", "content": content}


class TestToolSpec:
    """Tests for ToolSpec class."""

    def test_to_api_format(self):
        spec = ToolSpec(
            name="test_tool",
            description="A test tool",
            parameters={
                "properties": {"arg1": {"type": "string"}},
                "required": ["arg1"],
            },
            implementation=lambda: None,
        )

        api_format = spec.to_api()

        assert api_format["name"] == "test_tool"
        assert api_format["description"] == "A test tool"
        assert api_format["input_schema"]["type"] == "object"
        assert "arg1" in api_format["input_schema"]["properties"]


class TestAgentWithMockedClient:
    """Tests for Agent with mocked Anthropic client."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Anthropic client."""
        with patch("agentself.agent.anthropic.Anthropic") as mock:
            yield mock.return_value

    @pytest.fixture
    def agent(self, mock_client):
        """Create an agent with mocked client."""
        return Agent(system_prompt="Test prompt")

    def test_agent_initialization(self, agent):
        """Test that agent initializes correctly."""
        assert agent.system_prompt == "Test prompt"
        assert agent.model == "claude-sonnet-4-20250514"
        assert len(agent.messages) == 0

    def test_agent_has_self_awareness_tools(self, agent):
        """Test that agent has built-in self-awareness tools."""
        tool_names = list(agent._tool_specs.keys())
        assert "list_tools" in tool_names
        assert "read_tool_source" in tool_names
        assert "read_my_source" in tool_names
        assert "get_my_state" in tool_names

    def test_agent_has_self_modification_tools(self, agent):
        """Test that agent has self-modification tools."""
        tool_names = list(agent._tool_specs.keys())
        assert "modify_tool" in tool_names
        assert "add_tool" in tool_names
        assert "modify_system_prompt" in tool_names
        assert "commit_changes" in tool_names
        assert "rollback_changes" in tool_names

    def test_list_tools(self, agent):
        """Test the list_tools tool."""
        result = agent.list_tools()
        assert "Available tools:" in result
        assert "list_tools" in result

    def test_get_my_state(self, agent):
        """Test the get_my_state tool."""
        import json

        result = agent.get_my_state()
        state = json.loads(result)
        assert "model" in state
        assert "tools" in state
        assert "message_count" in state


class TestSelfModification:
    """Tests for self-modification capabilities."""

    @pytest.fixture
    def mock_client(self):
        with patch("agentself.agent.anthropic.Anthropic") as mock:
            yield mock.return_value

    @pytest.fixture
    def agent(self, mock_client):
        return Agent()

    def test_add_tool(self, agent):
        """Test adding a new tool at runtime."""
        code = '''
def new_tool(self, x: int) -> int:
    """Double a number."""
    return x * 2
'''
        result = agent.add_tool("new_tool", code)
        assert "added" in result.lower()
        assert "new_tool" in agent._tool_specs

    def test_add_tool_duplicate_error(self, agent):
        """Test that adding a duplicate tool fails."""
        result = agent.add_tool("list_tools", "def list_tools(self): pass")
        assert "Error" in result
        assert "already exists" in result

    def test_modify_tool(self, agent):
        """Test modifying an existing tool."""
        # First add a tool
        agent.add_tool("greet", 'def greet(self, name: str) -> str:\n    """Greet."""\n    return f"Hi {name}"')

        # Then modify it
        new_code = '''
def greet(self, name: str) -> str:
    """Greet someone formally."""
    return f"Hello, {name}!"
'''
        result = agent.modify_tool("greet", new_code)
        assert "modified" in result.lower()

    def test_modify_nonexistent_tool(self, agent):
        """Test that modifying a nonexistent tool fails."""
        result = agent.modify_tool("nonexistent", "def nonexistent(self): pass")
        assert "Error" in result
        assert "not found" in result

    def test_get_uncommitted_changes_empty(self, agent):
        """Test getting changes when there are none."""
        result = agent.get_uncommitted_changes()
        assert "No uncommitted changes" in result

    def test_get_uncommitted_changes_after_modification(self, agent):
        """Test getting changes after modification."""
        code = '''def test_tool(self):
    """Test."""
    pass'''
        agent.add_tool("test_tool", code)
        result = agent.get_uncommitted_changes()
        assert "test_tool" in result

    def test_rollback_changes(self, agent):
        """Test rolling back uncommitted changes."""
        original_count = len(agent._tool_specs)
        code = '''def temp_tool(self):
    """Temp."""
    pass'''
        agent.add_tool("temp_tool", code)
        assert len(agent._tool_specs) > original_count

        agent.rollback_changes()
        # After rollback, we rebuild from registry which doesn't have temp_tool
        assert "temp_tool" not in agent._tool_specs

    def test_modify_system_prompt(self, agent):
        """Test modifying the system prompt."""
        original = agent.system_prompt
        agent.modify_system_prompt("New prompt")
        assert agent.system_prompt == "New prompt"
        assert agent._tracker._changes.prompt is not None
