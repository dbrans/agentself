"""Tests for the ChangeTracker."""

from unittest.mock import MagicMock, patch

import pytest

from agentself.tracker import AgentChanges, ChangeTracker, PromptChange, ToolChange


class TestToolChange:
    """Tests for ToolChange dataclass."""

    def test_creation(self):
        change = ToolChange(
            name="test",
            original_source="def test(): pass",
            current_source="def test(): return 1",
            current_impl=lambda: 1,
        )
        assert change.name == "test"
        assert change.timestamp > 0

    def test_as_dict(self):
        change = ToolChange(
            name="test",
            original_source="original",
            current_source="current",
            current_impl=lambda: None,
        )
        d = change.as_dict()
        assert d["name"] == "test"
        assert d["original_source"] == "original"
        assert d["current_source"] == "current"
        assert "timestamp" in d


class TestAgentChanges:
    """Tests for AgentChanges dataclass."""

    def test_no_modifications(self):
        changes = AgentChanges()
        assert not changes.has_modifications()
        assert changes.summary() == "No changes"

    def test_with_tool_changes(self):
        changes = AgentChanges()
        changes.tools["test"] = ToolChange(
            name="test",
            original_source=None,
            current_source="def test(): pass",
            current_impl=lambda: None,
        )
        assert changes.has_modifications()
        assert "test" in changes.summary()

    def test_with_prompt_change(self):
        changes = AgentChanges()
        changes.prompt = PromptChange(original="old", current="new")
        assert changes.has_modifications()
        assert "prompt" in changes.summary().lower()


class TestChangeTracker:
    """Tests for ChangeTracker."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        agent = MagicMock()
        agent.system_prompt = "Test prompt"
        agent._tool_specs = {}
        return agent

    def test_initialization(self, mock_agent):
        tracker = ChangeTracker(mock_agent)
        assert tracker._baseline_prompt == "Test prompt"
        assert not tracker.get_changes().has_modifications()

    def test_record_tool_change(self, mock_agent):
        tracker = ChangeTracker(mock_agent)
        tracker.record_tool_change("new_tool", lambda: None, "def new_tool(): pass")

        changes = tracker.get_changes()
        assert changes.has_modifications()
        assert "new_tool" in changes.tools

    def test_record_prompt_change(self, mock_agent):
        tracker = ChangeTracker(mock_agent)
        tracker.record_prompt_change("New prompt")

        changes = tracker.get_changes()
        assert changes.prompt is not None
        assert changes.prompt.current == "New prompt"

    def test_reset_baseline(self, mock_agent):
        tracker = ChangeTracker(mock_agent)
        tracker.record_tool_change("tool", lambda: None, "def tool(): pass")
        assert tracker.get_changes().has_modifications()

        tracker.reset_baseline()
        assert not tracker.get_changes().has_modifications()

    def test_get_modified_tool_names(self, mock_agent):
        tracker = ChangeTracker(mock_agent)
        tracker.record_tool_change("tool1", lambda: None, "def tool1(): pass")
        tracker.record_tool_change("tool2", lambda: None, "def tool2(): pass")

        names = tracker.get_modified_tool_names()
        assert "tool1" in names
        assert "tool2" in names

    def test_is_tool_modified(self, mock_agent):
        tracker = ChangeTracker(mock_agent)
        tracker.record_tool_change("modified", lambda: None, "def modified(): pass")

        assert tracker.is_tool_modified("modified")
        assert not tracker.is_tool_modified("unmodified")
