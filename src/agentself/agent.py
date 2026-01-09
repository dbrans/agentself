"""Core Agent implementation with metaclass-based tool registration.

The agent uses a simple, homoiconic design where tools are Python functions
decorated with @tool. The agent can introspect and modify its own tools at runtime.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

import anthropic

if TYPE_CHECKING:
    from agentself.tracker import ChangeTracker


@dataclass
class Message:
    """A message in the conversation history."""

    role: str  # "user", "assistant", or "system"
    content: str | list[dict]

    def to_api(self) -> dict:
        """Convert to API format."""
        return {"role": self.role, "content": self.content}


@dataclass
class ToolSpec:
    """Specification for a tool, used to generate the JSON schema."""

    name: str
    description: str
    parameters: dict[str, Any]
    implementation: Callable

    def to_api(self) -> dict:
        """Convert to Claude API tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters.get("properties", {}),
                "required": self.parameters.get("required", []),
            },
        }


def _python_type_to_json_schema(python_type: type) -> dict:
    """Convert a Python type annotation to JSON Schema."""
    if python_type is str:
        return {"type": "string"}
    elif python_type is int:
        return {"type": "integer"}
    elif python_type is float:
        return {"type": "number"}
    elif python_type is bool:
        return {"type": "boolean"}
    elif python_type is list:
        return {"type": "array"}
    elif python_type is dict:
        return {"type": "object"}
    elif hasattr(python_type, "__origin__"):  # Generic types like list[str]
        origin = python_type.__origin__
        if origin is list:
            args = getattr(python_type, "__args__", ())
            if args:
                return {"type": "array", "items": _python_type_to_json_schema(args[0])}
            return {"type": "array"}
        elif origin is dict:
            return {"type": "object"}
    return {"type": "string"}  # fallback


def _generate_tool_spec(func: Callable) -> ToolSpec:
    """Generate a ToolSpec from a function's signature and docstring."""
    sig = inspect.signature(func)
    hints = getattr(func, "__annotations__", {})

    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        param_type = hints.get(param_name, str)
        schema = _python_type_to_json_schema(param_type)

        properties[param_name] = schema

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return ToolSpec(
        name=func.__name__,
        description=func.__doc__ or f"Tool: {func.__name__}",
        parameters={"properties": properties, "required": required},
        implementation=func,
    )


def tool(func: Callable) -> Callable:
    """Decorator to mark a method as an agent tool.

    The decorated function's signature and docstring are used to
    generate the JSON schema for the tool.
    """
    func._is_tool = True
    return func


class AgentMeta(type):
    """Metaclass that collects tools from class methods."""

    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
        cls = super().__new__(mcs, name, bases, namespace)

        # Collect tools from the class and its bases
        tools = {}
        for base in reversed(cls.__mro__):
            for attr_name, attr_value in vars(base).items():
                if callable(attr_value) and getattr(attr_value, "_is_tool", False):
                    tools[attr_name] = attr_value

        cls._tool_registry = tools
        return cls


@dataclass
class Agent(metaclass=AgentMeta):
    """A self-improving coding agent.

    The agent can:
    - Call an LLM with tool definitions
    - Execute tools defined as decorated methods
    - Introspect its own source and tools
    - Modify its tools at runtime
    - Persist changes back to source files
    """

    system_prompt: str = "You are a helpful coding assistant."
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    messages: list[Message] = field(default_factory=list)

    # Runtime state
    _client: Optional[anthropic.Anthropic] = field(default=None, repr=False)
    _tool_specs: dict[str, ToolSpec] = field(default_factory=dict, repr=False)
    _tracker: Optional[ChangeTracker] = field(default=None, repr=False)
    _generations_dir: Path = field(default_factory=lambda: Path(".agentself/generations"))

    def __post_init__(self):
        """Initialize the agent after dataclass initialization."""
        self._client = anthropic.Anthropic()
        self._build_tool_specs()
        self._init_tracker()

    def _init_tracker(self):
        """Initialize the change tracker (lazy import to avoid circular dependency)."""
        from agentself.tracker import ChangeTracker

        self._tracker = ChangeTracker(self)

    def _build_tool_specs(self):
        """Build tool specifications from registered tools."""
        self._tool_specs = {}
        for name, func in self._tool_registry.items():
            # Bind the method to this instance
            bound_method = func.__get__(self, type(self))
            self._tool_specs[name] = _generate_tool_spec(bound_method)
            self._tool_specs[name].implementation = bound_method

    def _get_tools_for_api(self) -> list[dict]:
        """Get tool definitions in API format."""
        return [spec.to_api() for spec in self._tool_specs.values()]

    def _execute_tool(self, name: str, args: dict) -> Any:
        """Execute a tool by name with the given arguments."""
        if name not in self._tool_specs:
            return f"Error: Unknown tool '{name}'"

        spec = self._tool_specs[name]
        try:
            result = spec.implementation(**args)
            return result
        except Exception as e:
            return f"Error executing {name}: {e}"

    def chat(self, user_message: str) -> str:
        """Send a message and get a response, potentially using tools."""
        self.messages.append(Message(role="user", content=user_message))

        while True:
            # Call the API
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                tools=self._get_tools_for_api(),
                messages=[m.to_api() for m in self.messages],
            )

            # Handle the response
            if response.stop_reason == "end_turn":
                # Extract text content
                text_content = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text_content += block.text
                self.messages.append(Message(role="assistant", content=text_content))
                return text_content

            elif response.stop_reason == "tool_use":
                # Process tool calls
                assistant_content = []
                tool_results = []

                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            }
                        )
                        # Execute the tool
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(result),
                            }
                        )

                # Add assistant message with tool use
                self.messages.append(Message(role="assistant", content=assistant_content))
                # Add tool results
                self.messages.append(Message(role="user", content=tool_results))

            else:
                # Unexpected stop reason
                return f"Unexpected stop reason: {response.stop_reason}"

    # === Self-awareness tools ===

    @tool
    def list_tools(self) -> str:
        """List all available tools with their descriptions."""
        lines = ["Available tools:"]
        for name, spec in self._tool_specs.items():
            lines.append(f"  - {name}: {spec.description.split(chr(10))[0]}")
        return "\n".join(lines)

    @tool
    def read_tool_source(self, tool_name: str) -> str:
        """Read the source code of a specific tool."""
        if tool_name not in self._tool_specs:
            return f"Error: Tool '{tool_name}' not found"

        impl = self._tool_specs[tool_name].implementation
        try:
            source = inspect.getsource(impl)
            return source
        except OSError:
            return f"Error: Could not get source for '{tool_name}'"

    @tool
    def read_my_source(self) -> str:
        """Read this agent's complete source code."""
        try:
            return inspect.getsource(type(self))
        except OSError:
            return "Error: Could not get agent source"

    @tool
    def get_my_state(self) -> str:
        """Get the current state of this agent (non-sensitive fields)."""
        return json.dumps(
            {
                "model": self.model,
                "system_prompt": self.system_prompt[:100] + "..."
                if len(self.system_prompt) > 100
                else self.system_prompt,
                "message_count": len(self.messages),
                "tool_count": len(self._tool_specs),
                "tools": list(self._tool_specs.keys()),
            },
            indent=2,
        )

    # === Self-modification tools ===

    @tool
    def modify_tool(self, tool_name: str, new_code: str) -> str:
        """Modify an existing tool's implementation at runtime.

        The new_code should be a complete function definition including the
        def line and docstring. The function name must match tool_name.

        Example:
            modify_tool("greet", '''
            def greet(self, name: str) -> str:
                \"\"\"Greet someone by name.\"\"\"
                return f"Hello, {name}! Welcome!"
            ''')
        """
        if tool_name not in self._tool_specs:
            return f"Error: Tool '{tool_name}' not found. Use add_tool to create new tools."

        try:
            # Compile and execute the new code
            exec_globals = {"__builtins__": __builtins__}
            exec(new_code, exec_globals)

            # Get the function from executed code
            new_impl = exec_globals.get(tool_name)
            if new_impl is None:
                return f"Error: The code must define a function named '{tool_name}'"

            # Bind to self using functools.partial
            import functools

            bound_impl = functools.partial(new_impl, self)
            functools.update_wrapper(bound_impl, new_impl)

            # Update the tool spec
            self._tool_specs[tool_name] = _generate_tool_spec(bound_impl)
            self._tool_specs[tool_name].implementation = bound_impl

            # Record the change
            self._tracker.record_tool_change(tool_name, new_impl, new_code.strip())

            return f"Tool '{tool_name}' modified. Use commit_changes() to persist."

        except SyntaxError as e:
            return f"Syntax error in new code: {e}"
        except Exception as e:
            return f"Error modifying tool: {e}"

    @tool
    def add_tool(self, tool_name: str, code: str) -> str:
        """Add a new tool to this agent at runtime.

        The code should be a complete function definition including the
        def line and docstring.

        Example:
            add_tool("calculate", '''
            def calculate(self, expression: str) -> str:
                \"\"\"Evaluate a mathematical expression.\"\"\"
                return str(eval(expression))
            ''')
        """
        if tool_name in self._tool_specs:
            return f"Error: Tool '{tool_name}' already exists. Use modify_tool to update it."

        try:
            # Compile and execute the new code
            exec_globals = {"__builtins__": __builtins__}
            exec(code, exec_globals)

            # Get the function from executed code
            new_impl = exec_globals.get(tool_name)
            if new_impl is None:
                return f"Error: The code must define a function named '{tool_name}'"

            # Bind to self using functools.partial
            import functools

            bound_impl = functools.partial(new_impl, self)
            functools.update_wrapper(bound_impl, new_impl)

            # Add the tool spec
            self._tool_specs[tool_name] = _generate_tool_spec(bound_impl)
            self._tool_specs[tool_name].implementation = bound_impl

            # Record the change
            self._tracker.record_tool_change(tool_name, new_impl, code.strip())

            return f"Tool '{tool_name}' added. Use commit_changes() to persist."

        except SyntaxError as e:
            return f"Syntax error in code: {e}"
        except Exception as e:
            return f"Error adding tool: {e}"

    @tool
    def modify_system_prompt(self, new_prompt: str) -> str:
        """Modify this agent's system prompt at runtime."""
        self.system_prompt = new_prompt
        self._tracker.record_prompt_change(new_prompt)
        return "System prompt updated. Use commit_changes() to persist."

    @tool
    def get_uncommitted_changes(self) -> str:
        """Get a summary of all uncommitted modifications."""
        changes = self._tracker.get_changes()
        if not changes.has_modifications():
            return "No uncommitted changes."
        return changes.summary()

    @tool
    def commit_changes(self, message: str = "Agent self-modification") -> str:
        """Persist all runtime modifications to source files.

        This writes the modified tools and prompts to a generated Python file
        that can be version-controlled and loaded in future sessions.
        """
        from agentself.generator import SourceGenerator, write_generated_source

        changes = self._tracker.get_changes()
        if not changes.has_modifications():
            return "No changes to commit."

        try:
            generator = SourceGenerator(self)
            generated = generator.generate_modified_tools_module(changes)

            if not generated.is_valid:
                return f"Error: Generated source is invalid: {generated.validation_error}"

            # Write to generations directory
            output_path = write_generated_source(generated, self._generations_dir)

            # Reset the tracker baseline
            self._tracker.reset_baseline()

            return f"Changes committed to {output_path}"

        except Exception as e:
            return f"Error committing changes: {e}"

    @tool
    def rollback_changes(self) -> str:
        """Discard all uncommitted modifications and restore to baseline."""
        changes = self._tracker.get_changes()
        if not changes.has_modifications():
            return "No changes to rollback."

        # Rebuild tool specs from original implementations
        self._build_tool_specs()

        # Reset tracker
        self._tracker.reset_baseline()

        return "All uncommitted changes rolled back."
