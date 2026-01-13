"""Tests for the SandboxedAgent class."""

from unittest.mock import MagicMock, patch

import pytest

from agentself.agent import SandboxedAgent, Message, AgentConfig, DEFAULT_SYSTEM_PROMPT
from agentself.sandbox import Sandbox
from agentself.capabilities import FileSystemCapability, UserCommunicationCapability
from agentself.permissions import AutoApproveHandler


class TestMessage:
    """Tests for Message class."""

    def test_to_api_format(self):
        msg = Message(role="user", content="Hello")
        assert msg.to_api() == {"role": "user", "content": "Hello"}

    def test_to_dict(self):
        msg = Message(role="user", content="Hello")
        d = msg.to_dict()
        assert d == {"role": "user", "content": "Hello"}

    def test_from_dict(self):
        d = {"role": "assistant", "content": "Hi there"}
        msg = Message.from_dict(d)
        assert msg.role == "assistant"
        assert msg.content == "Hi there"


class TestAgentConfig:
    """Tests for AgentConfig class."""

    def test_default_values(self):
        config = AgentConfig()
        assert config.model == "claude-sonnet-4-20250514"
        assert config.max_tokens == 4096
        assert config.max_retries == 3

    def test_custom_values(self):
        config = AgentConfig(model="custom-model", max_tokens=1000)
        assert config.model == "custom-model"
        assert config.max_tokens == 1000


class TestSandboxedAgentWithMockedClient:
    """Tests for SandboxedAgent with mocked Anthropic client."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Anthropic client."""
        with patch("agentself.agent.anthropic.Anthropic") as mock:
            yield mock.return_value

    @pytest.fixture
    def agent(self, mock_client):
        """Create an agent with mocked client."""
        return SandboxedAgent()

    def test_agent_initialization(self, agent):
        """Test that agent initializes correctly."""
        assert agent.config.model == "claude-sonnet-4-20250514"
        assert len(agent.messages) == 0

    def test_agent_has_default_capabilities(self, agent):
        """Test that agent has default capabilities."""
        cap_names = list(agent.sandbox.capabilities.keys())
        assert "fs" in cap_names
        assert "user" in cap_names
        assert "self" in cap_names
        assert "cmd" in cap_names

    def test_describe(self, agent):
        """Test the describe method."""
        desc = agent.describe()
        assert "SandboxedAgent" in desc
        assert "Capabilities" in desc

    def test_execute_runs_in_sandbox(self, agent):
        """Test that execute() runs code in sandbox."""
        result = agent.execute("1 + 1")
        assert result.success
        assert result.return_value == 2

    def test_execute_can_use_capabilities(self, agent):
        """Test that execute() can access capabilities."""
        result = agent.execute("user.say('hello')")
        assert result.success

    def test_analyze_code(self, agent):
        """Test analyze() shows what code will do."""
        plan = agent.analyze("user.say('test')")
        assert plan.success
        assert len(plan.calls) == 1
        assert plan.calls[0].capability_name == "user"

    def test_extract_code_blocks(self, agent):
        """Test code block extraction from markdown."""
        text = """
Here's some code:
```python
x = 1
```
And more:
```python
y = 2
```
"""
        blocks = agent._extract_code_blocks(text)
        assert len(blocks) == 2
        assert "x = 1" in blocks[0]
        assert "y = 2" in blocks[1]

    def test_build_capability_docs(self, agent):
        """Test capability documentation building."""
        docs = agent._build_capability_docs()
        assert "fs" in docs
        assert "user" in docs
        assert "cmd" in docs


class TestSandboxedAgentCreation:
    """Tests for SandboxedAgent creation."""

    @pytest.fixture
    def mock_client(self):
        with patch("agentself.agent.anthropic.Anthropic") as mock:
            yield mock.return_value

    def test_default_agent_has_capabilities(self, mock_client):
        """Test creating agent with default capabilities."""
        agent = SandboxedAgent()

        assert "fs" in agent.sandbox.capabilities
        assert "user" in agent.sandbox.capabilities
        assert "self" in agent.sandbox.capabilities
        assert "cmd" in agent.sandbox.capabilities

    def test_with_capabilities_class_method(self, mock_client):
        """Test with_capabilities class method."""
        agent = SandboxedAgent.with_capabilities(
            capabilities={
                "fs": FileSystemCapability(),
                "user": UserCommunicationCapability(),
            }
        )

        assert "fs" in agent.sandbox.capabilities
        assert "user" in agent.sandbox.capabilities
        assert "cmd" not in agent.sandbox.capabilities

    def test_interactive_class_method(self, mock_client, tmp_path):
        """Test interactive class method."""
        agent = SandboxedAgent.interactive(
            allowed_paths=[tmp_path],
            allowed_commands=["echo", "ls"],
        )

        assert "fs" in agent.sandbox.capabilities
        assert "cmd" in agent.sandbox.capabilities

    def test_empty_sandbox(self, mock_client):
        """Test creating agent with empty sandbox."""
        agent = SandboxedAgent(sandbox=Sandbox())

        assert len(agent.sandbox.capabilities) == 0

    def test_custom_config(self, mock_client):
        """Test creating agent with custom config."""
        config = AgentConfig(model="custom-model", max_tokens=2000)
        agent = SandboxedAgent(config=config)

        assert agent.config.model == "custom-model"
        assert agent.config.max_tokens == 2000


class TestSandboxedAgentSessionManagement:
    """Tests for session management."""

    @pytest.fixture
    def mock_client(self):
        with patch("agentself.agent.anthropic.Anthropic") as mock:
            yield mock.return_value

    @pytest.fixture
    def agent(self, mock_client):
        return SandboxedAgent()

    def test_clear_history(self, agent):
        """Test clearing conversation history."""
        agent.messages.append(Message(role="user", content="test"))
        agent.clear_history()

        assert len(agent.messages) == 0

    def test_reset(self, agent):
        """Test full reset."""
        agent.messages.append(Message(role="user", content="test"))
        agent.sandbox.execute("x = 42")

        agent.reset()

        assert len(agent.messages) == 0
        # Variable should be gone
        result = agent.sandbox.execute("x")
        assert not result.success

    def test_save_and_load_session(self, agent, tmp_path):
        """Test saving and loading session."""
        agent.messages.append(Message(role="user", content="Hello"))
        agent.messages.append(Message(role="assistant", content="Hi there"))

        session_file = tmp_path / "session.json"
        agent.save_session(session_file)

        # Create new agent and load
        new_agent = SandboxedAgent()
        new_agent.load_session(session_file)

        assert len(new_agent.messages) == 2
        assert new_agent.messages[0].content == "Hello"
        assert new_agent.messages[1].content == "Hi there"


class TestSandboxedAgentIntrospection:
    """Tests for agent introspection."""

    @pytest.fixture
    def mock_client(self):
        with patch("agentself.agent.anthropic.Anthropic") as mock:
            yield mock.return_value

    @pytest.fixture
    def agent(self, mock_client):
        return SandboxedAgent()

    def test_get_capabilities(self, agent):
        """Test getting capabilities."""
        caps = agent.get_capabilities()
        assert "fs" in caps
        assert "user" in caps

    def test_get_history(self, agent):
        """Test getting execution history."""
        agent.execute("x = 1")
        agent.execute("y = 2")

        history = agent.get_history()
        assert len(history) == 2
