"""Tests for the SourceGenerator."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agentself.generator import GeneratedSource, SourceGenerator, write_generated_source
from agentself.tracker import AgentChanges, PromptChange, ToolChange


class TestGeneratedSource:
    """Tests for GeneratedSource dataclass."""

    def test_valid_source(self):
        source = GeneratedSource(
            filename="test.py",
            content="x = 1",
            is_valid=True,
        )
        assert source.is_valid
        assert source.validation_error is None

    def test_invalid_source(self):
        source = GeneratedSource(
            filename="test.py",
            content="invalid python(",
            is_valid=False,
            validation_error="Syntax error",
        )
        assert not source.is_valid


class TestSourceGenerator:
    """Tests for SourceGenerator."""

    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock()
        agent._tool_specs = {}
        return agent

    @pytest.fixture
    def generator(self, mock_agent):
        return SourceGenerator(mock_agent)

    def test_validate_valid_source(self, generator):
        is_valid, error = generator.validate_source("x = 1\ny = 2")
        assert is_valid
        assert error is None

    def test_validate_invalid_source(self, generator):
        is_valid, error = generator.validate_source("def broken(")
        assert not is_valid
        assert "Syntax error" in error

    def test_generate_tool_source_adds_decorator(self, generator):
        source = "def my_tool(self):\n    pass"
        result = generator.generate_tool_source("my_tool", source)
        assert "@tool" in result

    def test_generate_tool_source_preserves_decorator(self, generator):
        source = "@tool\ndef my_tool(self):\n    pass"
        result = generator.generate_tool_source("my_tool", source)
        # Should not double-decorate
        assert result.count("@tool") == 1

    def test_generate_modified_tools_module(self, generator):
        changes = AgentChanges()
        changes.tools["test_tool"] = ToolChange(
            name="test_tool",
            original_source=None,
            current_source='def test_tool(self):\n    """Test."""\n    pass',
            current_impl=lambda: None,
        )

        result = generator.generate_modified_tools_module(changes)

        assert result.is_valid
        assert "test_tool" in result.content
        assert "from agentself import tool" in result.content

    def test_generate_diff(self, generator):
        changes = AgentChanges()
        changes.prompt = PromptChange(original="Old prompt", current="New prompt")
        changes.tools["my_tool"] = ToolChange(
            name="my_tool",
            original_source="old",
            current_source="new",
            current_impl=lambda: None,
        )

        diff = generator.generate_diff(changes)

        assert "System Prompt" in diff
        assert "my_tool" in diff


class TestWriteGeneratedSource:
    """Tests for write_generated_source function."""

    def test_write_valid_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = GeneratedSource(
                filename="test.py",
                content="x = 1",
                is_valid=True,
            )
            output_path = write_generated_source(source, Path(tmpdir))

            assert output_path.exists()
            assert output_path.read_text() == "x = 1"

    def test_write_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "nested" / "dir"
            source = GeneratedSource(
                filename="test.py",
                content="x = 1",
                is_valid=True,
            )
            output_path = write_generated_source(source, nested)

            assert output_path.exists()

    def test_write_invalid_source_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = GeneratedSource(
                filename="test.py",
                content="invalid",
                is_valid=False,
                validation_error="Bad syntax",
            )
            with pytest.raises(ValueError, match="invalid source"):
                write_generated_source(source, Path(tmpdir))
