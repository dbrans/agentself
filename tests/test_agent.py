"""Tests for the SandboxedAgent class."""

from unittest.mock import MagicMock, patch

import pytest

from agentself.agent import SandboxedAgent, Message, DEFAULT_SYSTEM_PROMPT
from agentself.sandbox import Sandbox


class TestMessage:
    """Tests for Message class."""

    def test_to_api_format(self):
        msg = Message(role="user", content="Hello")
        assert msg.to_api() == {"role": "user", "content": "Hello"}


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
        return SandboxedAgent.with_default_capabilities()

    def test_agent_initialization(self, agent):
        """Test that agent initializes correctly."""
        assert agent.model == "claude-sonnet-4-20250514"
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

    def test_with_default_capabilities(self, mock_client):
        """Test creating agent with default capabilities."""
        agent = SandboxedAgent.with_default_capabilities()
        
        assert "fs" in agent.sandbox.capabilities
        assert "user" in agent.sandbox.capabilities
        assert "self" in agent.sandbox.capabilities
        assert "cmd" in agent.sandbox.capabilities

    def test_custom_allowed_paths(self, mock_client, tmp_path):
        """Test creating agent with custom allowed paths."""
        agent = SandboxedAgent.with_default_capabilities(
            allowed_paths=[tmp_path]
        )
        
        fs = agent.sandbox.capabilities["fs"]
        assert tmp_path.resolve() in fs.allowed_paths

    def test_custom_allowed_commands(self, mock_client):
        """Test creating agent with custom allowed commands."""
        agent = SandboxedAgent.with_default_capabilities(
            allowed_commands=["git", "npm"]
        )
        
        cmd = agent.sandbox.capabilities["cmd"]
        assert cmd.allowed_commands == ["git", "npm"]

    def test_empty_sandbox(self, mock_client):
        """Test creating agent with empty sandbox."""
        agent = SandboxedAgent(sandbox=Sandbox())
        
        assert len(agent.sandbox.capabilities) == 0
