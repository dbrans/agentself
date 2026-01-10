"""Sandboxed Agent that uses capabilities for controlled access.

The agent runs LLM-generated Python code in a restricted sandbox.
Capabilities are injected to provide controlled access to resources.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import anthropic

from agentself.capabilities.base import Capability
from agentself.capabilities.file_system import FileSystemCapability
from agentself.capabilities.user_communication import UserCommunicationCapability
from agentself.capabilities.self_source import SelfSourceCapability
from agentself.capabilities.command_line import CommandLineCapability
from agentself.sandbox import Sandbox, ExecutionResult


@dataclass
class Message:
    """A message in the conversation history."""

    role: str  # "user", "assistant"
    content: str

    def to_api(self) -> dict:
        """Convert to API format."""
        return {"role": self.role, "content": self.content}


@dataclass
class SandboxedAgent:
    """A sandboxed coding agent that executes Python in a restricted environment.

    The agent:
    - Receives natural language requests
    - Generates Python code to fulfill them
    - Executes code in a sandbox with only granted capabilities
    - Returns results to the user
    """

    system_prompt: str = field(default_factory=lambda: DEFAULT_SYSTEM_PROMPT)
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    messages: list[Message] = field(default_factory=list)

    # Sandbox and capabilities
    sandbox: Sandbox = field(default_factory=Sandbox)
    
    # Runtime state
    _client: Optional[anthropic.Anthropic] = field(default=None, repr=False)

    def __post_init__(self):
        """Initialize the agent after dataclass initialization."""
        self._client = anthropic.Anthropic()
        
        # Connect SelfSourceCapability to our sandbox if present
        for cap in self.sandbox.capabilities.values():
            if hasattr(cap, "_sandbox"):
                cap._sandbox = self.sandbox

    @classmethod
    def with_default_capabilities(
        cls,
        allowed_paths: list[Path | str] | None = None,
        allowed_commands: list[str] | None = None,
        **kwargs,
    ) -> "SandboxedAgent":
        """Create an agent with standard capabilities.
        
        Args:
            allowed_paths: Paths for file system access. Defaults to current directory.
            allowed_commands: Allowed shell commands. Defaults to safe commands.
            **kwargs: Additional arguments passed to SandboxedAgent.
        """
        if allowed_paths is None:
            allowed_paths = [Path.cwd()]
        
        if allowed_commands is None:
            allowed_commands = ["ls", "cat", "head", "tail", "grep", "find", "echo"]
        
        capabilities = {
            "fs": FileSystemCapability(allowed_paths=allowed_paths),
            "user": UserCommunicationCapability(),
            "self": SelfSourceCapability(source_dir=Path("src/agentself")),
            "cmd": CommandLineCapability(allowed_commands=allowed_commands),
        }
        
        sandbox = Sandbox(capabilities=capabilities)
        return cls(sandbox=sandbox, **kwargs)

    def chat(self, user_message: str) -> str:
        """Send a message and get a response.
        
        The LLM will generate Python code that executes in the sandbox.
        """
        self.messages.append(Message(role="user", content=user_message))

        # Build the capability documentation for the prompt
        cap_docs = self._build_capability_docs()

        # Call the API
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system_prompt + "\n\n" + cap_docs,
            messages=[m.to_api() for m in self.messages],
        )

        # Extract the response text
        assistant_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                assistant_text += block.text

        self.messages.append(Message(role="assistant", content=assistant_text))

        # Extract and execute any Python code blocks
        code_blocks = self._extract_code_blocks(assistant_text)
        
        if code_blocks:
            results = []
            for code in code_blocks:
                result = self.sandbox.execute(code)
                results.append(result)
            
            # If there were code executions, add the results as context
            if any(not r.success for r in results):
                # Report errors back to get fixes
                error_msg = self._format_execution_results(results)
                return f"{assistant_text}\n\n---\n\n**Execution Results:**\n{error_msg}"
            else:
                # Success - return any output
                output = self._format_execution_results(results)
                if output.strip():
                    return f"{assistant_text}\n\n---\n\n**Output:**\n{output}"
        
        return assistant_text

    def execute(self, code: str) -> ExecutionResult:
        """Execute Python code directly in the sandbox.
        
        Useful for interactive/REPL usage.
        """
        return self.sandbox.execute(code)

    def _build_capability_docs(self) -> str:
        """Build documentation of available capabilities."""
        lines = ["## Available Capabilities\n"]
        lines.append("You have access to the following capability objects in the sandbox:\n")
        
        for name, cap in self.sandbox.capabilities.items():
            lines.append(f"### `{name}`")
            lines.append(f"```\n{cap.describe()}\n```\n")
        
        return "\n".join(lines)

    def _extract_code_blocks(self, text: str) -> list[str]:
        """Extract Python code blocks from markdown text."""
        blocks = []
        in_block = False
        current_block = []
        
        for line in text.split("\n"):
            if line.strip().startswith("```python"):
                in_block = True
                current_block = []
            elif line.strip() == "```" and in_block:
                in_block = False
                if current_block:
                    blocks.append("\n".join(current_block))
            elif in_block:
                current_block.append(line)
        
        return blocks

    def _format_execution_results(self, results: list[ExecutionResult]) -> str:
        """Format execution results for display."""
        parts = []
        for i, result in enumerate(results):
            if len(results) > 1:
                parts.append(f"**Block {i + 1}:**")
            parts.append(str(result))
        return "\n".join(parts)

    def describe(self) -> str:
        """Get a description of the agent's current state."""
        lines = [
            f"SandboxedAgent (model: {self.model})",
            f"Messages: {len(self.messages)}",
            "",
            self.sandbox.describe(),
        ]
        return "\n".join(lines)


DEFAULT_SYSTEM_PROMPT = """You are a sandboxed coding agent. You operate inside a restricted Python environment where only specific capabilities are available.

When the user asks you to do something:
1. Think about what capabilities you need
2. Write Python code using the available capabilities
3. Put your code in ```python``` code blocks

The code will be executed in a sandbox. You do NOT have access to:
- import statements (no importing modules)
- open() or file() (use the fs capability instead)
- subprocess or os.system (use the cmd capability instead)
- Network access (no requests, urllib, etc.)

You DO have access to:
- Basic Python (variables, functions, loops, etc.)
- Safe builtins (len, range, sorted, etc.)
- The capability objects documented below

Always use the capabilities for external operations. For example:
- To read a file: `fs.read("path/to/file")`
- To run a command: `cmd.run("ls -la")`
- To message the user: `user.say("Hello!")`

If you're unsure what capabilities are available, you can inspect them:
- `caps` - dictionary of all capabilities
- `fs.describe()` - get details about a capability
"""
