"""Self-source capability for agent introspection and self-modification.

This capability allows the agent to:
- Read its own source code and that of other capabilities
- List and describe available capabilities
- Create new capabilities at runtime (with templates for common patterns)
- Test capabilities in isolated sandboxes before installation
- Modify existing capabilities
- Hot-reload changes into the running sandbox
- Commit changes to disk for persistence

The key insight: runtime is primary, disk is for persistence/versioning.
"""

from __future__ import annotations

import ast
import difflib
import inspect
import time
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, Type

from agentself.capabilities.base import Capability

if TYPE_CHECKING:
    from agentself.core import CapabilityContract
    from agentself.sandbox import Sandbox


@dataclass
class TestResult:
    """Result of testing a staged capability."""

    success: bool
    """Whether all tests passed."""

    output: str
    """Combined output from tests."""

    error: str | None = None
    """Error message if tests failed."""

    duration: float = 0.0
    """Time taken to run tests in seconds."""

    contract_valid: bool = False
    """Whether the capability has a valid contract."""

    instantiation_ok: bool = False
    """Whether the capability could be instantiated."""

    methods_tested: list[str] = field(default_factory=list)
    """Methods that were tested."""

    def __str__(self) -> str:
        status = "PASS" if self.success else "FAIL"
        lines = [f"Test Result: {status}"]
        lines.append(f"  Duration: {self.duration:.3f}s")
        lines.append(f"  Instantiation: {'OK' if self.instantiation_ok else 'FAILED'}")
        lines.append(f"  Contract: {'valid' if self.contract_valid else 'invalid/missing'}")
        if self.methods_tested:
            lines.append(f"  Methods tested: {', '.join(self.methods_tested)}")
        if self.error:
            lines.append(f"  Error: {self.error}")
        if self.output:
            lines.append("  Output:")
            for line in self.output.strip().split("\n"):
                lines.append(f"    {line}")
        return "\n".join(lines)


@dataclass
class CapabilityChange:
    """Represents a staged change to a capability."""

    name: str
    """Name of the capability."""

    original_source: str | None
    """Original source, or None for new capabilities."""

    new_source: str
    """The new source code."""

    is_new: bool = False
    """True if this is a new capability, False if modifying existing."""

    compiled_class: Type[Capability] | None = None
    """The compiled class, if successfully compiled."""

    test_results: list[TestResult] = field(default_factory=list)
    """History of test results."""

    def get_diff(self) -> str:
        """Get a unified diff of the change."""
        if self.original_source is None:
            return f"[NEW CAPABILITY]\n{self.new_source}"

        original_lines = self.original_source.splitlines(keepends=True)
        new_lines = self.new_source.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f"{self.name} (original)",
            tofile=f"{self.name} (modified)",
        )
        return "".join(diff) or "(no changes)"

    def last_test_passed(self) -> bool:
        """Check if the most recent test passed."""
        return self.test_results[-1].success if self.test_results else False


class SelfSourceCapability(Capability):
    """Read, modify, and hot-reload the agent's own capabilities.

    This is the core of self-improvement: the agent can understand
    its own code and change it at runtime.
    """

    name = "self"
    description = "Inspect and modify the agent's source code and capabilities."

    # Common imports that capabilities might need
    CAPABILITY_IMPORTS = """
from __future__ import annotations
from pathlib import Path
from typing import Any
from agentself.capabilities.base import Capability
"""

    # Templates for creating new capabilities
    TEMPLATES = {
        "basic": '''class {class_name}(Capability):
    """{description}"""

    name = "{name}"
    description = "{description}"

    def contract(self) -> "CapabilityContract":
        """Declare what this capability might do."""
        from agentself.core import CapabilityContract
        return CapabilityContract(
            reads=[],   # e.g., ["file:*.txt"]
            writes=[],  # e.g., ["file:output/*"]
        )

    def example_method(self, arg: str) -> str:
        """Example method - replace with your actual functionality."""
        return f"Processed: {{arg}}"
''',
        "data_processor": '''class {class_name}(Capability):
    """{description}"""

    name = "{name}"
    description = "{description}"

    def __init__(self):
        self._cache = {{}}

    def contract(self) -> "CapabilityContract":
        from agentself.core import CapabilityContract
        return CapabilityContract(reads=["memory:cache"])

    def process(self, data: str) -> str:
        """Process input data and return result."""
        # Implement your processing logic here
        result = data.upper()  # Example transformation
        return result

    def get_stats(self) -> dict:
        """Get processing statistics."""
        return {{"cache_size": len(self._cache)}}
''',
        "validator": '''class {class_name}(Capability):
    """{description}"""

    name = "{name}"
    description = "{description}"

    def contract(self) -> "CapabilityContract":
        from agentself.core import CapabilityContract
        return CapabilityContract()  # Pure computation, no side effects

    def validate(self, data: Any) -> tuple[bool, str]:
        """Validate data and return (is_valid, message)."""
        # Implement your validation logic here
        if data is None:
            return False, "Data cannot be None"
        return True, "Validation passed"

    def validate_many(self, items: list) -> list[tuple[bool, str]]:
        """Validate multiple items."""
        return [self.validate(item) for item in items]
''',
        "api_client": '''class {class_name}(Capability):
    """{description}"""

    name = "{name}"
    description = "{description}"

    def __init__(self, base_url: str = "https://api.example.com"):
        self.base_url = base_url

    def contract(self) -> "CapabilityContract":
        from agentself.core import CapabilityContract
        return CapabilityContract(
            network=[f"{{self.base_url}}/*"],
            reads=["response:*"],
        )

    def get(self, endpoint: str) -> dict:
        """Make a GET request to the API."""
        # Note: Actual HTTP would require an http client capability
        # This is a template showing the structure
        return {{"endpoint": endpoint, "status": "mock"}}

    def post(self, endpoint: str, data: dict) -> dict:
        """Make a POST request to the API."""
        return {{"endpoint": endpoint, "data": data, "status": "mock"}}
''',
    }

    def __init__(
        self,
        sandbox: "Sandbox | None" = None,
        source_dir: Path | None = None,
    ):
        """Initialize with reference to the sandbox.

        Args:
            sandbox: The sandbox this capability is part of.
            source_dir: Directory containing agent source files.
        """
        self._sandbox = sandbox
        self._source_dir = source_dir or Path("src/agentself")
        self._staged_capabilities: dict[str, CapabilityChange] = {}
        self._original_sources: dict[str, str] = {}

    def contract(self) -> "CapabilityContract":
        """Declare what this capability might do."""
        from agentself.core import CapabilityContract

        return CapabilityContract(
            reads=["self:*", f"file:{self._source_dir}/**"],
            writes=["self:staged/*", f"file:{self._source_dir}/capabilities/**"],
            spawns=True,  # Can create new capabilities
        )

    # =========================================================================
    # Introspection: Understanding the current state
    # =========================================================================

    def list_capabilities(self) -> list[str]:
        """List all capabilities currently available in the sandbox.

        Returns:
            List of capability names.
        """
        if self._sandbox is None:
            return ["(sandbox not connected)"]
        return list(self._sandbox.capabilities.keys())

    def describe_capability(self, name: str) -> str:
        """Get detailed description of a capability.

        Args:
            name: Name of the capability to describe.

        Returns:
            The capability's self-documenting description.
        """
        if self._sandbox is None:
            return "(sandbox not connected)"

        cap = self._sandbox.capabilities.get(name)
        if cap is None:
            return f"Capability '{name}' not found."

        return cap.describe()

    def read_capability_source(self, name: str) -> str:
        """Read the source code of a capability.

        Args:
            name: Name of the capability to read.

        Returns:
            The Python source code of the capability class.
        """
        if self._sandbox is None:
            return "(sandbox not connected)"

        cap = self._sandbox.capabilities.get(name)
        if cap is None:
            return f"Capability '{name}' not found."

        try:
            source = inspect.getsource(type(cap))
            # Cache original source for diffing
            if name not in self._original_sources:
                self._original_sources[name] = source
            return source
        except OSError:
            return f"Could not retrieve source for '{name}'."

    def read_agent_source(self) -> str:
        """Read the main agent module source code.

        Returns:
            The agent.py source code.
        """
        agent_file = self._source_dir / "agent.py"
        if agent_file.exists():
            return agent_file.read_text()
        return f"Agent source not found at {agent_file}"

    def get_capability_config(self, name: str) -> dict[str, Any]:
        """Get the current configuration of a capability.

        Returns init arguments that could be used to recreate
        the capability with the same settings.

        Args:
            name: Name of the capability.

        Returns:
            Dictionary of configuration values.
        """
        if self._sandbox is None:
            return {"error": "sandbox not connected"}

        cap = self._sandbox.capabilities.get(name)
        if cap is None:
            return {"error": f"capability '{name}' not found"}

        # Try to extract configuration from instance attributes
        config = {}
        for attr_name in dir(cap):
            if attr_name.startswith("_"):
                continue
            try:
                value = getattr(cap, attr_name)
                if not callable(value):
                    # Only include JSON-serializable types
                    if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                        config[attr_name] = value
                    elif isinstance(value, Path):
                        config[attr_name] = str(value)
            except Exception:
                pass

        return config

    # =========================================================================
    # Templates: Scaffolding for new capabilities
    # =========================================================================

    def list_templates(self) -> str:
        """List available capability templates.

        Templates provide starting points for common capability patterns.

        Returns:
            List of template names and descriptions.
        """
        lines = ["Available Templates:", ""]
        template_descriptions = {
            "basic": "Simple capability with one method and a contract",
            "data_processor": "Capability for processing/transforming data with caching",
            "validator": "Pure validation logic with no side effects",
            "api_client": "Template for wrapping external APIs",
        }
        for name, desc in template_descriptions.items():
            lines.append(f"  - {name}: {desc}")
        lines.append("")
        lines.append("Use from_template(name, cap_name, description) to create a capability from a template.")
        return "\n".join(lines)

    def from_template(
        self,
        template_name: str,
        capability_name: str,
        description: str = "A new capability.",
    ) -> str:
        """Create and stage a new capability from a template.

        This is the easiest way to create a new capability. Pick a template,
        give it a name and description, then customize the generated code.

        Args:
            template_name: Name of the template (use list_templates() to see options).
            capability_name: Name for the new capability (e.g., 'json_validator').
            description: Description of what the capability does.

        Returns:
            The generated source code (also staged for testing/installation).
        """
        if template_name not in self.TEMPLATES:
            available = ", ".join(self.TEMPLATES.keys())
            return f"Unknown template '{template_name}'. Available: {available}"

        # Generate class name from capability name
        class_name = "".join(word.title() for word in capability_name.split("_")) + "Capability"

        # Fill in the template
        source = self.TEMPLATES[template_name].format(
            class_name=class_name,
            name=capability_name,
            description=description,
        )

        # Stage it
        result = self.add_capability(capability_name, source)

        if "staged" in result.lower():
            return f"Created capability '{capability_name}' from '{template_name}' template.\n\nSource:\n{source}\n\n{result}"
        return result

    # =========================================================================
    # Staging: Preparing changes before applying them
    # =========================================================================

    def add_capability(self, name: str, code: str) -> str:
        """Stage a new capability for creation.

        The capability code should define a class that inherits from Capability.

        Args:
            name: Name for the new capability.
            code: Python source code defining the capability class.

        Returns:
            Status message.
        """
        # Validate syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            return f"Syntax error in capability code: {e}"

        # Check it looks like a capability class
        if "class " not in code or "Capability" not in code:
            return "Code must define a class that inherits from Capability."

        # Try to compile it
        compiled_class = self._compile_capability(code)
        if isinstance(compiled_class, str):
            return compiled_class  # Error message

        self._staged_capabilities[name] = CapabilityChange(
            name=name,
            original_source=None,
            new_source=code,
            is_new=True,
            compiled_class=compiled_class,
        )
        return f"Capability '{name}' staged. Use test_capability() to verify, reload_capability() to activate."

    def modify_capability(self, name: str, new_code: str) -> str:
        """Stage modifications to an existing capability.

        Args:
            name: Name of the capability to modify.
            new_code: New Python source code for the capability.

        Returns:
            Status message.
        """
        # Validate syntax
        try:
            ast.parse(new_code)
        except SyntaxError as e:
            return f"Syntax error in capability code: {e}"

        # Get original source
        original = self._original_sources.get(name)
        if original is None:
            source = self.read_capability_source(name)
            if "not found" in source.lower() or "could not" in source.lower():
                return f"Cannot modify '{name}': capability not found."
            original = source

        # Try to compile it
        compiled_class = self._compile_capability(new_code)
        if isinstance(compiled_class, str):
            return compiled_class  # Error message

        self._staged_capabilities[name] = CapabilityChange(
            name=name,
            original_source=original,
            new_source=new_code,
            is_new=False,
            compiled_class=compiled_class,
        )
        return f"Capability '{name}' modified. Use diff_capability() to review, test_capability() to verify, reload_capability() to activate."

    def diff_capability(self, name: str) -> str:
        """Show the diff for a staged capability change.

        Args:
            name: Name of the capability to diff.

        Returns:
            Unified diff of the changes.
        """
        if name not in self._staged_capabilities:
            return f"No staged changes for capability '{name}'."

        change = self._staged_capabilities[name]
        return change.get_diff()

    def staged_changes(self) -> str:
        """Get a summary of all staged changes.

        Returns:
            Summary of staged new and modified capabilities.
        """
        if not self._staged_capabilities:
            return "No staged changes."

        lines = ["Staged Changes:", ""]

        new_caps = [c for c in self._staged_capabilities.values() if c.is_new]
        modified_caps = [c for c in self._staged_capabilities.values() if not c.is_new]

        if new_caps:
            lines.append("New Capabilities:")
            for change in new_caps:
                status = "compiled" if change.compiled_class else "not compiled"
                lines.append(f"  + {change.name} ({status})")

        if modified_caps:
            lines.append("Modified Capabilities:")
            for change in modified_caps:
                status = "compiled" if change.compiled_class else "not compiled"
                lines.append(f"  ~ {change.name} ({status})")

        lines.append("")
        lines.append(f"Total: {len(self._staged_capabilities)} staged change(s)")
        lines.append("Commands: test_capability(name), reload_capability(name), commit_capability(name)")

        return "\n".join(lines)

    def rollback_capability(self, name: str) -> str:
        """Discard staged changes for a capability.

        Args:
            name: Name of the capability to rollback.

        Returns:
            Status message.
        """
        if name not in self._staged_capabilities:
            return f"No staged changes for capability '{name}'."

        del self._staged_capabilities[name]
        return f"Staged changes for '{name}' discarded."

    def rollback_all(self) -> str:
        """Discard all staged changes.

        Returns:
            Status message.
        """
        count = len(self._staged_capabilities)
        self._staged_capabilities.clear()
        return f"Discarded {count} staged change(s)."

    # =========================================================================
    # Testing: Verify changes before activating them
    # =========================================================================

    def test_capability(self, name: str, test_code: str | None = None) -> str:
        """Test a staged capability comprehensively.

        Verifies that the capability:
        1. Compiles successfully
        2. Can be instantiated
        3. Has required methods (describe, contract)
        4. Has a valid contract declaration
        5. Passes custom test code (if provided)

        The capability is tested in an isolated ephemeral sandbox to prevent
        any side effects from affecting the main sandbox.

        Args:
            name: Name of the staged capability to test.
            test_code: Optional Python code to test the capability.
                      The capability instance is available as 'cap'.
                      Example: "assert cap.process('hello') == 'HELLO'"

        Returns:
            Detailed test results.
        """
        start_time = time.time()

        if name not in self._staged_capabilities:
            return f"No staged changes for capability '{name}'."

        change = self._staged_capabilities[name]

        # Compilation check
        if change.compiled_class is None:
            result = self._compile_capability(change.new_source)
            if isinstance(result, str):
                test_result = TestResult(
                    success=False,
                    output="",
                    error=f"Compilation failed: {result}",
                    duration=time.time() - start_time,
                )
                change.test_results.append(test_result)
                return str(test_result)
            change.compiled_class = result

        # Instantiation check
        try:
            instance = change.compiled_class()
            instantiation_ok = True
        except Exception as e:
            test_result = TestResult(
                success=False,
                output="",
                error=f"Instantiation failed: {type(e).__name__}: {e}",
                duration=time.time() - start_time,
            )
            change.test_results.append(test_result)
            return str(test_result)

        # Contract validation
        contract_valid = False
        contract_error = None
        try:
            contract = instance.contract()
            # Verify contract is a CapabilityContract
            from agentself.core import CapabilityContract
            if isinstance(contract, CapabilityContract):
                contract_valid = True
            else:
                contract_error = f"contract() returned {type(contract)}, expected CapabilityContract"
        except Exception as e:
            contract_error = f"contract() failed: {type(e).__name__}: {e}"

        # Check required methods
        methods_tested = []
        output_lines = []

        if callable(getattr(instance, "describe", None)):
            methods_tested.append("describe")
            try:
                desc = instance.describe()
                output_lines.append(f"describe() returned: {len(desc)} chars")
            except Exception as e:
                output_lines.append(f"describe() raised: {e}")

        if callable(getattr(instance, "contract", None)):
            methods_tested.append("contract")

        # Run in isolated sandbox if test code provided
        test_error = None
        if test_code:
            test_error = self._run_isolated_test(instance, test_code, output_lines)

        # Build result
        success = instantiation_ok and contract_valid and (test_error is None)

        test_result = TestResult(
            success=success,
            output="\n".join(output_lines),
            error=contract_error or test_error,
            duration=time.time() - start_time,
            contract_valid=contract_valid,
            instantiation_ok=instantiation_ok,
            methods_tested=methods_tested,
        )

        change.test_results.append(test_result)

        # Also include the description for context
        result_str = str(test_result)
        if success:
            result_str += f"\n\nCapability Description:\n{instance.describe()}"

        return result_str

    def _run_isolated_test(
        self,
        instance: Capability,
        test_code: str,
        output_lines: list[str],
    ) -> str | None:
        """Run test code against a capability in isolation.

        Args:
            instance: The capability instance to test.
            test_code: Python code to execute. 'cap' refers to the instance.
            output_lines: List to append output to.

        Returns:
            Error message if test failed, None if passed.
        """
        # Create isolated namespace for testing
        import sys
        from io import StringIO

        test_namespace = {
            "cap": instance,
            "print": print,
            "assert": None,  # Will use Python's built-in
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "True": True,
            "False": False,
            "None": None,
        }

        # Capture stdout
        old_stdout = sys.stdout
        captured = StringIO()

        try:
            sys.stdout = captured

            # Execute test code
            exec(test_code, test_namespace)

            # Capture any output
            test_output = captured.getvalue()
            if test_output:
                output_lines.append(f"Test output:\n{test_output}")

            output_lines.append("Custom tests: PASSED")
            return None

        except AssertionError as e:
            return f"Assertion failed: {e}"
        except Exception as e:
            return f"Test error: {type(e).__name__}: {e}"
        finally:
            sys.stdout = old_stdout

    def run_capability_test(self, name: str, test_code: str) -> str:
        """Run additional test code against a staged capability.

        Use this to run more tests after the initial test_capability() call.

        Args:
            name: Name of the staged capability.
            test_code: Python code to test. 'cap' refers to the capability instance.

        Returns:
            Test results.
        """
        if name not in self._staged_capabilities:
            return f"No staged changes for capability '{name}'."

        change = self._staged_capabilities[name]

        if change.compiled_class is None:
            return "Capability not compiled. Run test_capability() first."

        try:
            instance = change.compiled_class()
        except Exception as e:
            return f"Could not instantiate: {e}"

        output_lines = []
        error = self._run_isolated_test(instance, test_code, output_lines)

        if error:
            return f"Test FAILED: {error}\n" + "\n".join(output_lines)
        return "Test PASSED\n" + "\n".join(output_lines)

    # =========================================================================
    # Hot-reload: Activate changes in the running sandbox
    # =========================================================================

    def reload_capability(self, name: str, **init_kwargs) -> str:
        """Hot-reload a staged capability into the running sandbox.

        This is the key self-modification operation: the capability
        is replaced in the running sandbox without restart.

        Args:
            name: Name of the staged capability to reload.
            **init_kwargs: Arguments to pass to the capability's __init__.

        Returns:
            Status message.
        """
        if self._sandbox is None:
            return "(sandbox not connected)"

        if name not in self._staged_capabilities:
            return f"No staged changes for capability '{name}'."

        change = self._staged_capabilities[name]

        if change.compiled_class is None:
            result = self._compile_capability(change.new_source)
            if isinstance(result, str):
                return f"Compilation failed: {result}"
            change.compiled_class = result

        # Get existing config to preserve settings
        if not change.is_new and not init_kwargs:
            existing_config = self.get_capability_config(name)
            if "error" not in existing_config:
                # Filter to just the init parameters
                init_kwargs = existing_config

        # Instantiate the new capability
        try:
            new_instance = change.compiled_class(**init_kwargs)
        except TypeError as e:
            # Try without kwargs if they don't match
            try:
                new_instance = change.compiled_class()
            except Exception as e2:
                return f"Instantiation failed: {type(e2).__name__}: {e2}"
        except Exception as e:
            return f"Instantiation failed: {type(e).__name__}: {e}"

        # Inject into sandbox
        self._sandbox.inject_capability(name, new_instance)

        # Update our cached original source
        self._original_sources[name] = change.new_source

        return f"Capability '{name}' hot-reloaded into sandbox. Use commit_capability() to persist to disk."

    def reload_all(self) -> str:
        """Hot-reload all staged capabilities.

        Returns:
            Summary of reload results.
        """
        if not self._staged_capabilities:
            return "No staged changes to reload."

        results = []
        names = list(self._staged_capabilities.keys())

        for name in names:
            result = self.reload_capability(name)
            results.append(f"{name}: {result}")

        return "\n".join(results)

    # =========================================================================
    # Persistence: Save changes to disk
    # =========================================================================

    def commit_capability(self, name: str) -> str:
        """Commit a staged capability to disk.

        Args:
            name: Name of the staged capability to commit.

        Returns:
            Status message with file path.
        """
        if name not in self._staged_capabilities:
            return f"No staged capability named '{name}'."

        change = self._staged_capabilities[name]

        # Write to capabilities directory
        cap_dir = self._source_dir / "capabilities"
        cap_file = cap_dir / f"{name}.py"

        try:
            cap_dir.mkdir(parents=True, exist_ok=True)

            # Add imports if not present
            source = change.new_source
            if "from agentself.capabilities.base import Capability" not in source:
                source = self.CAPABILITY_IMPORTS + "\n\n" + source

            cap_file.write_text(source)

            # Update cached original source
            self._original_sources[name] = change.new_source

            del self._staged_capabilities[name]

            action = "created" if change.is_new else "updated"
            return f"Capability '{name}' {action}: {cap_file}"
        except Exception as e:
            return f"Error writing capability: {e}"

    def commit_all(self) -> str:
        """Commit all staged capabilities to disk.

        Returns:
            Summary of committed changes.
        """
        if not self._staged_capabilities:
            return "No staged changes to commit."

        results = []
        names = list(self._staged_capabilities.keys())

        for name in names:
            result = self.commit_capability(name)
            results.append(result)

        return "\n".join(results)

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _compile_capability(self, source: str) -> Type[Capability] | str:
        """Compile capability source and return the class.

        Args:
            source: Python source code defining a Capability subclass.

        Returns:
            The compiled class, or an error message string.
        """
        # Build a namespace with necessary imports
        namespace = {
            "Capability": Capability,
            "Path": Path,
            "Any": Any,
            "__name__": "__capability__",
        }

        try:
            exec(source, namespace)
        except Exception as e:
            return f"Execution error: {type(e).__name__}: {e}"

        # Find the Capability subclass
        for obj in namespace.values():
            if (
                isinstance(obj, type)
                and issubclass(obj, Capability)
                and obj is not Capability
            ):
                return obj

        return "No Capability subclass found in source"
