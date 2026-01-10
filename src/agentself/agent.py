"""Sandboxed Agent with LLM integration.

The agent orchestrates:
1. Conversation with the LLM
2. Code extraction from LLM responses
3. Two-phase execution in the sandbox
4. Error feedback and retry loops
5. Session persistence

The key architectural insight: the agent doesn't just execute code,
it shows the LLM what code will do (via analyze()) and feeds back
actual results, creating a tight feedback loop.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

import anthropic

from agentself.capabilities.base import Capability
from agentself.capabilities.command_line import CommandLineCapability
from agentself.capabilities.file_system import FileSystemCapability
from agentself.capabilities.self_source import SelfSourceCapability
from agentself.capabilities.user_communication import UserCommunicationCapability
from agentself.core import ExecutionPlan, ExecutionResult
from agentself.permissions import (
    AutoApproveHandler,
    InteractiveHandler,
    PermissionHandler,
    PolicyHandler,
)
from agentself.sandbox import Sandbox


@dataclass
class Message:
    """A message in the conversation history."""

    role: str  # "user", "assistant"
    content: str

    def to_api(self) -> dict:
        """Convert to Anthropic API format."""
        return {"role": self.role, "content": self.content}

    def to_dict(self) -> dict:
        """Convert to serializable dict."""
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Create from serialized dict."""
        return cls(role=data["role"], content=data["content"])


@dataclass
class ConversationTurn:
    """A complete turn in the conversation."""

    user_message: str
    assistant_response: str
    code_blocks: list[str] = field(default_factory=list)
    execution_results: list[ExecutionResult] = field(default_factory=list)
    plans: list[ExecutionPlan] = field(default_factory=list)


@dataclass
class AgentConfig:
    """Configuration for the agent."""

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    max_retries: int = 3
    show_plans: bool = True
    auto_approve_reads: bool = True


class SandboxedAgent:
    """A sandboxed coding agent that executes LLM-generated Python code.

    The agent:
    1. Receives natural language requests
    2. Sends them to the LLM with capability documentation
    3. Extracts Python code from the response
    4. Analyzes what the code will do (two-phase execution)
    5. Requests permission if needed
    6. Executes and captures results
    7. Feeds results back to the LLM for iteration

    The sandbox ensures the LLM can only do what capabilities allow,
    and the permission system enables human oversight.
    """

    def __init__(
        self,
        sandbox: Sandbox | None = None,
        config: AgentConfig | None = None,
        system_prompt: str | None = None,
    ):
        """Initialize the agent.

        Args:
            sandbox: The execution sandbox. If None, creates one with default capabilities.
            config: Agent configuration. If None, uses defaults.
            system_prompt: Custom system prompt. If None, uses default.
        """
        self.config = config or AgentConfig()
        self.sandbox = sandbox or self._create_default_sandbox()
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.messages: list[Message] = []
        self.turns: list[ConversationTurn] = []
        self._client = anthropic.Anthropic()

        # Connect capabilities that need sandbox reference
        self._connect_capabilities()

    def _create_default_sandbox(self) -> Sandbox:
        """Create a sandbox with default capabilities and permission handler."""
        # Create a sensible default permission policy
        if self.config.auto_approve_reads:
            handler = PolicyHandler()
            handler.allow("fs", "read")
            handler.allow("fs", "list")
            handler.allow("fs", "exists")
            handler.allow("self")  # Allow all self-introspection
            handler.allow("user")  # Allow user communication
            # Writes and commands need explicit approval
        else:
            handler = AutoApproveHandler()

        capabilities = {
            "fs": FileSystemCapability(allowed_paths=[Path.cwd()]),
            "user": UserCommunicationCapability(),
            "self": SelfSourceCapability(source_dir=Path("src/agentself")),
            "cmd": CommandLineCapability(
                allowed_commands=["ls", "cat", "head", "tail", "grep", "find", "echo", "pwd"]
            ),
        }

        return Sandbox(capabilities=capabilities, permission_handler=handler)

    def _connect_capabilities(self) -> None:
        """Connect capabilities that need references to other components."""
        for cap in self.sandbox.capabilities.values():
            if hasattr(cap, "_sandbox"):
                cap._sandbox = self.sandbox

    @classmethod
    def with_capabilities(
        cls,
        capabilities: dict[str, Capability],
        permission_handler: PermissionHandler | None = None,
        **kwargs,
    ) -> "SandboxedAgent":
        """Create an agent with custom capabilities.

        Args:
            capabilities: Dict of name -> Capability.
            permission_handler: Custom permission handler.
            **kwargs: Additional arguments for SandboxedAgent.
        """
        sandbox = Sandbox(
            capabilities=capabilities,
            permission_handler=permission_handler or AutoApproveHandler(),
        )
        return cls(sandbox=sandbox, **kwargs)

    @classmethod
    def interactive(
        cls,
        allowed_paths: list[Path | str] | None = None,
        allowed_commands: list[str] | None = None,
        **kwargs,
    ) -> "SandboxedAgent":
        """Create an agent with interactive permission prompts.

        Each capability call will prompt the user for approval.

        Args:
            allowed_paths: Paths for file system access.
            allowed_commands: Allowed shell commands.
            **kwargs: Additional arguments for SandboxedAgent.
        """
        if allowed_paths is None:
            allowed_paths = [Path.cwd()]

        if allowed_commands is None:
            allowed_commands = ["ls", "cat", "head", "tail", "grep", "find", "echo", "pwd"]

        capabilities = {
            "fs": FileSystemCapability(allowed_paths=[Path(p) for p in allowed_paths]),
            "user": UserCommunicationCapability(),
            "self": SelfSourceCapability(source_dir=Path("src/agentself")),
            "cmd": CommandLineCapability(allowed_commands=allowed_commands),
        }

        sandbox = Sandbox(
            capabilities=capabilities,
            permission_handler=InteractiveHandler(),
        )
        return cls(sandbox=sandbox, **kwargs)

    # =========================================================================
    # Main conversation interface
    # =========================================================================

    def chat(self, user_message: str) -> str:
        """Send a message and get a response.

        This is the main interface for interacting with the agent.
        The agent will:
        1. Send your message to the LLM
        2. Extract and execute any Python code in the response
        3. Feed execution results back to the LLM if needed
        4. Return the final response

        Args:
            user_message: The user's message.

        Returns:
            The agent's response, potentially including execution results.
        """
        self.messages.append(Message(role="user", content=user_message))

        # Build context with capability documentation
        full_system = self._build_system_prompt()

        # Get LLM response
        response = self._call_llm(full_system, self.messages)
        self.messages.append(Message(role="assistant", content=response))

        # Extract and execute code blocks
        code_blocks = self._extract_code_blocks(response)

        if not code_blocks:
            # No code to execute, just return the response
            self.turns.append(
                ConversationTurn(
                    user_message=user_message,
                    assistant_response=response,
                )
            )
            return response

        # Execute code blocks with retry loop
        all_results: list[ExecutionResult] = []
        all_plans: list[ExecutionPlan] = []
        retry_count = 0

        for code in code_blocks:
            result = self.sandbox.execute(code)
            all_results.append(result)
            if result.plan:
                all_plans.append(result.plan)

        # Check if any execution failed
        has_errors = any(not r.success for r in all_results)

        if has_errors and retry_count < self.config.max_retries:
            # Feed errors back to LLM for correction
            error_feedback = self._format_error_feedback(all_results)
            self.messages.append(Message(role="user", content=error_feedback))

            retry_response = self._call_llm(full_system, self.messages)
            self.messages.append(Message(role="assistant", content=retry_response))

            # Try executing the new code
            new_code_blocks = self._extract_code_blocks(retry_response)
            for code in new_code_blocks:
                result = self.sandbox.execute(code)
                all_results.append(result)
                if result.plan:
                    all_plans.append(result.plan)

            response = retry_response

        # Build the final response with execution results
        turn = ConversationTurn(
            user_message=user_message,
            assistant_response=response,
            code_blocks=code_blocks,
            execution_results=all_results,
            plans=all_plans,
        )
        self.turns.append(turn)

        return self._format_response_with_results(response, all_results)

    def execute(self, code: str) -> ExecutionResult:
        """Execute Python code directly in the sandbox.

        Useful for interactive/REPL usage without going through the LLM.

        Args:
            code: Python code to execute.

        Returns:
            The execution result.
        """
        return self.sandbox.execute(code)

    def analyze(self, code: str) -> ExecutionPlan:
        """Analyze code without executing it.

        Shows what the code would do (which capabilities it would use)
        without actually doing it.

        Args:
            code: Python code to analyze.

        Returns:
            The execution plan.
        """
        return self.sandbox.analyze(code)

    # =========================================================================
    # Streaming interface
    # =========================================================================

    def chat_stream(self, user_message: str) -> Iterator[str]:
        """Stream a response token by token.

        Yields tokens as they arrive from the LLM.
        Code execution happens after streaming completes.

        Args:
            user_message: The user's message.

        Yields:
            Response tokens.
        """
        self.messages.append(Message(role="user", content=user_message))
        full_system = self._build_system_prompt()

        response_parts = []

        with self._client.messages.stream(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=full_system,
            messages=[m.to_api() for m in self.messages],
        ) as stream:
            for text in stream.text_stream:
                response_parts.append(text)
                yield text

        full_response = "".join(response_parts)
        self.messages.append(Message(role="assistant", content=full_response))

        # Execute code blocks
        code_blocks = self._extract_code_blocks(full_response)
        if code_blocks:
            yield "\n\n---\n\n**Executing code...**\n\n"
            for code in code_blocks:
                result = self.sandbox.execute(code)
                yield f"```\n{result}\n```\n"

    # =========================================================================
    # Session management
    # =========================================================================

    def save_session(self, path: Path | str) -> None:
        """Save the conversation history to a file.

        Args:
            path: Path to save the session.
        """
        path = Path(path)
        data = {
            "messages": [m.to_dict() for m in self.messages],
            "config": {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "max_retries": self.config.max_retries,
            },
        }
        path.write_text(json.dumps(data, indent=2))

    def load_session(self, path: Path | str) -> None:
        """Load a conversation history from a file.

        Args:
            path: Path to load the session from.
        """
        path = Path(path)
        data = json.loads(path.read_text())
        self.messages = [Message.from_dict(m) for m in data["messages"]]
        if "config" in data:
            self.config.model = data["config"].get("model", self.config.model)
            self.config.max_tokens = data["config"].get("max_tokens", self.config.max_tokens)

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.messages = []
        self.turns = []

    def reset(self) -> None:
        """Reset the agent completely (history and sandbox state)."""
        self.clear_history()
        self.sandbox.reset()

    # =========================================================================
    # Introspection
    # =========================================================================

    def describe(self) -> str:
        """Get a description of the agent's current state."""
        lines = [
            f"SandboxedAgent",
            f"  Model: {self.config.model}",
            f"  Messages: {len(self.messages)}",
            f"  Turns: {len(self.turns)}",
            "",
            self.sandbox.describe(),
        ]
        return "\n".join(lines)

    def get_capabilities(self) -> dict[str, Capability]:
        """Get the current capabilities."""
        return self.sandbox.capabilities.copy()

    def get_history(self) -> list[ExecutionResult]:
        """Get the execution history from the sandbox."""
        return self.sandbox.get_history()

    # =========================================================================
    # Internal methods
    # =========================================================================

    def _build_system_prompt(self) -> str:
        """Build the full system prompt with capability documentation."""
        cap_docs = self._build_capability_docs()
        return f"{self.system_prompt}\n\n{cap_docs}"

    def _build_capability_docs(self) -> str:
        """Build documentation of available capabilities."""
        lines = ["## Available Capabilities\n"]
        lines.append("You have access to the following capability objects in the sandbox:\n")

        for name, cap in self.sandbox.capabilities.items():
            lines.append(f"### `{name}`")
            lines.append(f"```\n{cap.describe()}\n```\n")

        return "\n".join(lines)

    def _call_llm(self, system: str, messages: list[Message]) -> str:
        """Call the LLM and return the response text."""
        response = self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=system,
            messages=[m.to_api() for m in messages],
        )

        # Extract text from response
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)

        return "".join(text_parts)

    def _extract_code_blocks(self, text: str) -> list[str]:
        """Extract Python code blocks from markdown text."""
        # Match ```python ... ``` blocks
        pattern = r"```python\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        return [m.strip() for m in matches if m.strip()]

    def _format_error_feedback(self, results: list[ExecutionResult]) -> str:
        """Format execution errors for feedback to the LLM."""
        errors = [r for r in results if not r.success]
        if not errors:
            return ""

        lines = ["The following errors occurred during execution:\n"]
        for i, result in enumerate(errors, 1):
            lines.append(f"**Error {i}:**")
            lines.append(f"```\n{result.error}\n```\n")

        lines.append("Please fix the code and try again.")
        return "\n".join(lines)

    def _format_response_with_results(
        self,
        response: str,
        results: list[ExecutionResult],
    ) -> str:
        """Format the response with execution results appended."""
        if not results:
            return response

        parts = [response, "\n---\n"]

        has_errors = any(not r.success for r in results)
        header = "**Execution Results:**" if not has_errors else "**Execution Results (with errors):**"
        parts.append(f"\n{header}\n")

        for i, result in enumerate(results):
            if len(results) > 1:
                parts.append(f"\n**Block {i + 1}:**\n")
            parts.append(f"```\n{result}\n```\n")

        return "".join(parts)


DEFAULT_SYSTEM_PROMPT = """You are a sandboxed coding agent. You operate inside a restricted Python environment where only specific capabilities are available.

When the user asks you to do something:
1. Think about what capabilities you need
2. Write Python code using the available capabilities
3. Put your code in ```python``` code blocks

The code will be executed in a sandbox with two-phase execution:
1. ANALYZE: Your code is analyzed to see what capabilities it will use
2. PERMISSION: The user may be asked to approve capability usage
3. EXECUTE: If approved, the code runs with real capabilities

You do NOT have access to:
- import statements (no importing modules)
- open() or file() (use the fs capability instead)
- subprocess or os.system (use the cmd capability instead)
- Network access (no requests, urllib, etc.)

You DO have access to:
- Basic Python (variables, functions, loops, conditionals, etc.)
- Safe builtins (len, range, sorted, print, etc.)
- The capability objects documented below

Always use the capabilities for external operations. For example:
- To read a file: `fs.read("path/to/file")`
- To list files: `fs.list("*.py")`
- To run a command: `cmd.run("ls -la")`
- To message the user: `user.say("Hello!")`
- To see your own capabilities: `self.list_capabilities()`
- To read your source: `self.read_capability_source("fs")`

You can define functions and use variables across code blocks in the same conversation.

If you make an error, I'll show you the error message and you can fix your code.
"""
