"""Core source capability for modifying the agent's core infrastructure.

This capability allows the agent to:
- Read source code of core modules (agent.py, sandbox.py, core.py, etc.)
- Stage modifications to core modules
- Test changes in isolated subprocesses (fork-exec pattern)
- Apply changes (requires restart for activation)
- Rollback to previous versions

Key differences from SelfSourceCapability:
- Core changes CANNOT be hot-reloaded (require restart)
- Testing happens in subprocess to avoid corrupting the running process
- Higher security requirements for approval
- Automatic versioning with rollback support

The hierarchy of modifiability:
- Layer 0 (IMMUTABLE): Permission enforcement kernel - cannot be modified
- Layer 1 (RESTART): Core modules - this capability manages these
- Layer 2 (HOT-RELOAD): Capabilities - managed by SelfSourceCapability
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentself.capabilities.base import Capability

if TYPE_CHECKING:
    from agentself.core import CapabilityContract
    from agentself.sandbox import Sandbox


# Core modules that can be modified (Layer 1)
CORE_MODULES = {
    "agent": "agent.py",
    "sandbox": "sandbox.py",
    "core": "core.py",
    "permissions": "permissions.py",
    "proxy": "proxy.py",
}

# Modules that are IMMUTABLE (Layer 0) - cannot be modified at runtime
IMMUTABLE_MODULES = {
    # None currently - but this is where we'd put security-critical code
    # e.g., "permission_kernel": "permission_kernel.py"
}


@dataclass
class CoreTestResult:
    """Result of testing a core change in subprocess."""

    success: bool
    """Whether all tests passed."""

    output: str
    """Combined stdout/stderr from test process."""

    error: str | None = None
    """Error message if tests failed."""

    duration: float = 0.0
    """Time taken to run tests in seconds."""

    exit_code: int = 0
    """Exit code of the test process."""

    syntax_valid: bool = False
    """Whether the code has valid Python syntax."""

    imports_valid: bool = False
    """Whether imports work correctly."""

    tests_passed: int = 0
    """Number of tests that passed."""

    tests_failed: int = 0
    """Number of tests that failed."""

    def __str__(self) -> str:
        status = "PASS" if self.success else "FAIL"
        lines = [f"Core Test Result: {status}"]
        lines.append(f"  Exit code: {self.exit_code}")
        lines.append(f"  Duration: {self.duration:.3f}s")
        lines.append(f"  Syntax: {'valid' if self.syntax_valid else 'INVALID'}")
        lines.append(f"  Imports: {'OK' if self.imports_valid else 'FAILED'}")
        if self.tests_passed or self.tests_failed:
            lines.append(f"  Tests: {self.tests_passed} passed, {self.tests_failed} failed")
        if self.error:
            lines.append(f"  Error: {self.error}")
        if self.output:
            lines.append("  Output:")
            for line in self.output.strip().split("\n")[-20:]:  # Last 20 lines
                lines.append(f"    {line}")
        return "\n".join(lines)


@dataclass
class CoreChange:
    """Represents a staged change to a core module."""

    module: str
    """Name of the module (e.g., 'agent', 'sandbox')."""

    original_source: str
    """Original source code."""

    new_source: str
    """The proposed new source code."""

    original_hash: str
    """SHA256 hash of original for integrity checking."""

    timestamp: float = field(default_factory=time.time)
    """When this change was staged."""

    test_results: list[CoreTestResult] = field(default_factory=list)
    """History of test results."""

    description: str = ""
    """Human-readable description of the change."""

    def get_diff(self) -> str:
        """Get a unified diff of the change."""
        original_lines = self.original_source.splitlines(keepends=True)
        new_lines = self.new_source.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f"{self.module}.py (original)",
            tofile=f"{self.module}.py (modified)",
        )
        return "".join(diff) or "(no changes)"

    def last_test_passed(self) -> bool:
        """Check if the most recent test passed."""
        return self.test_results[-1].success if self.test_results else False


@dataclass
class CoreVersion:
    """A saved version of a core module for rollback."""

    module: str
    """Name of the module."""

    source: str
    """The source code at this version."""

    hash: str
    """SHA256 hash of the source."""

    timestamp: float
    """When this version was saved."""

    description: str = ""
    """Description of this version."""

    def __str__(self) -> str:
        dt = datetime.fromtimestamp(self.timestamp)
        return f"{self.module} @ {dt.isoformat()} ({self.hash[:8]}): {self.description or 'no description'}"


class CoreSourceCapability(Capability):
    """Read, modify, and test the agent's core infrastructure.

    Unlike SelfSourceCapability which manages hot-reloadable capabilities,
    this manages the core modules that require a restart to take effect.

    Safety features:
    - Changes are tested in isolated subprocess before applying
    - Original versions are saved for rollback
    - Immutable modules cannot be modified
    - All changes are staged and require explicit application
    """

    name = "core"
    description = "Inspect and modify the agent's core source code (agent.py, sandbox.py, etc.)."

    def __init__(
        self,
        sandbox: "Sandbox | None" = None,
        source_dir: Path | None = None,
        versions_dir: Path | None = None,
    ):
        """Initialize with paths to source and version storage.

        Args:
            sandbox: The sandbox this capability is part of.
            source_dir: Directory containing agent source files.
            versions_dir: Directory for storing version history.
        """
        self._sandbox = sandbox
        self._source_dir = source_dir or Path("src/agentself")
        self._versions_dir = versions_dir or Path(".agentself/versions")
        self._staged_changes: dict[str, CoreChange] = {}
        self._version_history: dict[str, list[CoreVersion]] = {}

        # Load existing version history
        self._load_version_history()

    def contract(self) -> "CapabilityContract":
        """Declare what this capability might do."""
        from agentself.core import CapabilityContract

        return CapabilityContract(
            reads=[
                f"file:{self._source_dir}/*.py",
                f"file:{self._versions_dir}/**",
            ],
            writes=[
                f"file:{self._source_dir}/*.py",  # Core modules
                f"file:{self._versions_dir}/**",  # Version history
            ],
            executes=["subprocess:python *"],  # For testing
            spawns=True,  # Can spawn test processes
        )

    # =========================================================================
    # Introspection: Understanding the current state
    # =========================================================================

    def list_modules(self) -> dict[str, str]:
        """List all core modules that can be modified.

        Returns:
            Dict mapping module name to filename.
        """
        return CORE_MODULES.copy()

    def list_immutable(self) -> dict[str, str]:
        """List modules that cannot be modified (Layer 0).

        Returns:
            Dict mapping module name to filename.
        """
        return IMMUTABLE_MODULES.copy()

    def read_module(self, module: str) -> str:
        """Read the source code of a core module.

        Args:
            module: Module name (e.g., 'agent', 'sandbox', 'core').

        Returns:
            The Python source code.
        """
        if module not in CORE_MODULES:
            available = ", ".join(CORE_MODULES.keys())
            return f"Unknown module '{module}'. Available: {available}"

        module_path = self._source_dir / CORE_MODULES[module]
        if not module_path.exists():
            return f"Module file not found: {module_path}"

        return module_path.read_text()

    def describe_module(self, module: str) -> str:
        """Get a summary of a core module.

        Args:
            module: Module name.

        Returns:
            Summary including docstring, classes, and functions.
        """
        source = self.read_module(module)
        if source.startswith("Unknown") or source.startswith("Module"):
            return source

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return f"Syntax error in {module}: {e}"

        lines = [f"Module: {module} ({CORE_MODULES[module]})"]
        lines.append("")

        # Module docstring
        docstring = ast.get_docstring(tree)
        if docstring:
            lines.append("Docstring:")
            for line in docstring.split("\n")[:5]:  # First 5 lines
                lines.append(f"  {line}")
            lines.append("")

        # Classes
        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        if classes:
            lines.append("Classes:")
            for cls in classes:
                doc = ast.get_docstring(cls) or "No docstring"
                doc_first = doc.split("\n")[0]
                lines.append(f"  - {cls.name}: {doc_first}")
            lines.append("")

        # Functions
        functions = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if functions:
            lines.append("Functions:")
            for func in functions:
                doc = ast.get_docstring(func) or "No docstring"
                doc_first = doc.split("\n")[0]
                lines.append(f"  - {func.name}(): {doc_first}")

        return "\n".join(lines)

    def get_module_hash(self, module: str) -> str:
        """Get the SHA256 hash of a module's current source.

        Args:
            module: Module name.

        Returns:
            Hex-encoded SHA256 hash.
        """
        source = self.read_module(module)
        if source.startswith("Unknown") or source.startswith("Module"):
            return source
        return hashlib.sha256(source.encode()).hexdigest()

    # =========================================================================
    # Staging: Preparing changes before applying
    # =========================================================================

    def modify_module(self, module: str, new_source: str, description: str = "") -> str:
        """Stage a modification to a core module.

        The change is NOT applied immediately. Use test_module() to verify,
        then apply_module() to write to disk (requires restart).

        Args:
            module: Module name to modify.
            new_source: The new source code.
            description: Human-readable description of the change.

        Returns:
            Status message.
        """
        if module in IMMUTABLE_MODULES:
            return f"Module '{module}' is immutable and cannot be modified."

        if module not in CORE_MODULES:
            available = ", ".join(CORE_MODULES.keys())
            return f"Unknown module '{module}'. Available: {available}"

        # Validate syntax first
        try:
            ast.parse(new_source)
        except SyntaxError as e:
            return f"Syntax error in proposed change: {e}"

        # Read original source
        original = self.read_module(module)
        if original.startswith("Unknown") or original.startswith("Module"):
            return original

        # Save version before modifying (if not already staged)
        if module not in self._staged_changes:
            self._save_version(module, original, "Before staged modification")

        self._staged_changes[module] = CoreChange(
            module=module,
            original_source=original,
            new_source=new_source,
            original_hash=hashlib.sha256(original.encode()).hexdigest(),
            description=description,
        )

        return f"Module '{module}' staged for modification. Use test_module() to verify, then apply_module() to save."

    def diff_module(self, module: str) -> str:
        """Show the diff for a staged module change.

        Args:
            module: Module name.

        Returns:
            Unified diff of the changes.
        """
        if module not in self._staged_changes:
            return f"No staged changes for module '{module}'."

        return self._staged_changes[module].get_diff()

    def staged_changes(self) -> str:
        """Get a summary of all staged changes.

        Returns:
            Summary of staged module modifications.
        """
        if not self._staged_changes:
            return "No staged changes."

        lines = ["Staged Core Changes:", ""]

        for name, change in self._staged_changes.items():
            status_parts = []
            if change.test_results:
                last_test = change.test_results[-1]
                status_parts.append("tested" if last_test.success else "test failed")
            else:
                status_parts.append("not tested")
            status = ", ".join(status_parts)

            lines.append(f"  ~ {name}.py ({status})")
            if change.description:
                lines.append(f"    Description: {change.description}")

        lines.append("")
        lines.append(f"Total: {len(self._staged_changes)} staged change(s)")
        lines.append("")
        lines.append("Commands:")
        lines.append("  test_module(name)  - Test changes in subprocess")
        lines.append("  apply_module(name) - Write to disk (requires restart)")
        lines.append("  rollback_module(name) - Discard staged changes")

        return "\n".join(lines)

    def rollback_staged(self, module: str) -> str:
        """Discard staged changes for a module.

        Args:
            module: Module name.

        Returns:
            Status message.
        """
        if module not in self._staged_changes:
            return f"No staged changes for module '{module}'."

        del self._staged_changes[module]
        return f"Staged changes for '{module}' discarded."

    def rollback_all_staged(self) -> str:
        """Discard all staged changes.

        Returns:
            Status message.
        """
        count = len(self._staged_changes)
        self._staged_changes.clear()
        return f"Discarded {count} staged change(s)."

    # =========================================================================
    # Testing: Verify changes in isolated subprocess (fork-exec pattern)
    # =========================================================================

    def test_module(self, module: str, test_code: str | None = None) -> str:
        """Test a staged module change in an isolated subprocess.

        This is critical for core changes: we cannot hot-reload core modules,
        so we test by spawning a subprocess with the modified code.

        Args:
            module: Module name to test.
            test_code: Optional additional test code to run.

        Returns:
            Detailed test results.
        """
        start_time = time.time()

        if module not in self._staged_changes:
            return f"No staged changes for module '{module}'."

        change = self._staged_changes[module]

        # Step 1: Validate syntax
        try:
            ast.parse(change.new_source)
            syntax_valid = True
        except SyntaxError as e:
            result = CoreTestResult(
                success=False,
                output="",
                error=f"Syntax error: {e}",
                duration=time.time() - start_time,
                syntax_valid=False,
            )
            change.test_results.append(result)
            return str(result)

        # Step 2: Test in subprocess
        result = self._run_subprocess_test(module, change.new_source, test_code)
        result.syntax_valid = syntax_valid
        result.duration = time.time() - start_time

        change.test_results.append(result)
        return str(result)

    def _run_subprocess_test(
        self,
        module: str,
        new_source: str,
        test_code: str | None,
    ) -> CoreTestResult:
        """Run tests in an isolated subprocess.

        Creates a temporary directory with the modified module and runs
        import tests plus any custom test code.

        Args:
            module: Module being tested.
            new_source: The new source code.
            test_code: Optional custom test code.

        Returns:
            CoreTestResult with test outcomes.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create package structure
            pkg_dir = tmppath / "agentself"
            pkg_dir.mkdir()
            (pkg_dir / "__init__.py").write_text("")

            # Copy all core modules, replacing the one being tested
            for mod_name, mod_file in CORE_MODULES.items():
                source_path = self._source_dir / mod_file
                if source_path.exists():
                    if mod_name == module:
                        # Use the new source
                        (pkg_dir / mod_file).write_text(new_source)
                    else:
                        # Copy existing
                        (pkg_dir / mod_file).write_text(source_path.read_text())

            # Copy capabilities directory
            cap_src = self._source_dir / "capabilities"
            if cap_src.exists():
                cap_dst = pkg_dir / "capabilities"
                cap_dst.mkdir()
                (cap_dst / "__init__.py").write_text("")
                for cap_file in cap_src.glob("*.py"):
                    (cap_dst / cap_file.name).write_text(cap_file.read_text())

            # Build test script
            test_script = self._build_test_script(module, test_code)
            test_file = tmppath / "test_core_change.py"
            test_file.write_text(test_script)

            # Run test in subprocess
            try:
                proc = subprocess.run(
                    [sys.executable, str(test_file)],
                    cwd=str(tmppath),
                    capture_output=True,
                    text=True,
                    timeout=30,  # 30 second timeout
                    env={**dict(subprocess_env()), "PYTHONPATH": str(tmppath)},
                )

                success = proc.returncode == 0
                output = proc.stdout + proc.stderr

                # Parse test counts from output
                tests_passed = output.count("[PASS]")
                tests_failed = output.count("[FAIL]")

                return CoreTestResult(
                    success=success,
                    output=output,
                    error=None if success else f"Test process exited with code {proc.returncode}",
                    exit_code=proc.returncode,
                    imports_valid="[IMPORT OK]" in output,
                    tests_passed=tests_passed,
                    tests_failed=tests_failed,
                )

            except subprocess.TimeoutExpired:
                return CoreTestResult(
                    success=False,
                    output="",
                    error="Test timed out after 30 seconds",
                    exit_code=-1,
                )
            except Exception as e:
                return CoreTestResult(
                    success=False,
                    output="",
                    error=f"Failed to run test: {type(e).__name__}: {e}",
                    exit_code=-1,
                )

    def _build_test_script(self, module: str, test_code: str | None) -> str:
        """Build a test script to run in subprocess.

        Args:
            module: Module being tested.
            test_code: Optional custom test code.

        Returns:
            Python script content.
        """
        script_parts = [
            "#!/usr/bin/env python3",
            '"""Test script for core module change."""',
            "",
            "import sys",
            "import traceback",
            "",
            "def test_import():",
            '    """Test that the module can be imported."""',
            "    try:",
            f"        from agentself import {module}",
            '        print("[IMPORT OK]")',
            "        return True",
            "    except Exception as e:",
            '        print(f"[IMPORT FAIL] {type(e).__name__}: {e}")',
            "        traceback.print_exc()",
            "        return False",
            "",
        ]

        # Add module-specific tests based on what module is being tested
        if module == "core":
            script_parts.extend([
                "def test_core_types():",
                '    """Test that core types are defined correctly."""',
                "    try:",
                "        from agentself.core import (",
                "            CapabilityContract,",
                "            CapabilityCall,",
                "            ExecutionPlan,",
                "            ExecutionResult,",
                "            ExecutionMode,",
                "        )",
                "        # Verify they can be instantiated",
                "        contract = CapabilityContract()",
                "        assert hasattr(contract, 'reads')",
                "        assert hasattr(contract, 'writes')",
                '        print("[PASS] Core types OK")',
                "        return True",
                "    except Exception as e:",
                '        print(f"[FAIL] Core types: {e}")',
                "        return False",
                "",
            ])
        elif module == "sandbox":
            script_parts.extend([
                "def test_sandbox_class():",
                '    """Test that Sandbox class is defined correctly."""',
                "    try:",
                "        from agentself.sandbox import Sandbox, SAFE_BUILTINS",
                "        # Verify key attributes",
                "        assert hasattr(Sandbox, 'execute')",
                "        assert hasattr(Sandbox, 'analyze')",
                "        assert isinstance(SAFE_BUILTINS, dict)",
                '        print("[PASS] Sandbox class OK")',
                "        return True",
                "    except Exception as e:",
                '        print(f"[FAIL] Sandbox class: {e}")',
                "        return False",
                "",
            ])
        elif module == "agent":
            script_parts.extend([
                "def test_agent_class():",
                '    """Test that SandboxedAgent class is defined correctly."""',
                "    try:",
                "        from agentself.agent import SandboxedAgent, Message",
                "        assert hasattr(SandboxedAgent, 'chat')",
                "        assert hasattr(SandboxedAgent, 'execute')",
                "        assert hasattr(Message, 'to_api')",
                '        print("[PASS] Agent class OK")',
                "        return True",
                "    except Exception as e:",
                '        print(f"[FAIL] Agent class: {e}")',
                "        return False",
                "",
            ])
        elif module == "permissions":
            script_parts.extend([
                "def test_permissions():",
                '    """Test that permission system is defined correctly."""',
                "    try:",
                "        from agentself.permissions import (",
                "            PermissionDecision,",
                "            PermissionHandler,",
                "            AutoApproveHandler,",
                "            PolicyHandler,",
                "        )",
                "        handler = AutoApproveHandler()",
                "        assert callable(getattr(handler, 'check', None))",
                '        print("[PASS] Permission system OK")',
                "        return True",
                "    except Exception as e:",
                '        print(f"[FAIL] Permission system: {e}")',
                "        return False",
                "",
            ])

        # Add custom test code if provided
        if test_code:
            script_parts.extend([
                "def test_custom():",
                '    """Run custom test code."""',
                "    try:",
                f"        from agentself import {module}",
                f"        # Custom test code:",
                "        " + test_code.replace("\n", "\n        "),
                '        print("[PASS] Custom tests")',
                "        return True",
                "    except AssertionError as e:",
                '        print(f"[FAIL] Assertion: {e}")',
                "        return False",
                "    except Exception as e:",
                '        print(f"[FAIL] Custom test: {type(e).__name__}: {e}")',
                "        return False",
                "",
            ])

        # Main test runner
        script_parts.extend([
            "def main():",
            "    results = []",
            "    results.append(test_import())",
            "",
        ])

        # Call module-specific tests
        if module == "core":
            script_parts.append("    results.append(test_core_types())")
        elif module == "sandbox":
            script_parts.append("    results.append(test_sandbox_class())")
        elif module == "agent":
            script_parts.append("    results.append(test_agent_class())")
        elif module == "permissions":
            script_parts.append("    results.append(test_permissions())")

        if test_code:
            script_parts.append("    results.append(test_custom())")

        script_parts.extend([
            "",
            "    if all(results):",
            '        print("\\nAll tests passed!")',
            "        sys.exit(0)",
            "    else:",
            "        failed = results.count(False)",
            '        print(f"\\n{failed} test(s) failed")',
            "        sys.exit(1)",
            "",
            'if __name__ == "__main__":',
            "    main()",
        ])

        return "\n".join(script_parts)

    # =========================================================================
    # Application: Write changes to disk (requires restart)
    # =========================================================================

    def apply_module(self, module: str, force: bool = False) -> str:
        """Apply a staged module change to disk.

        WARNING: Changes take effect on next restart.

        Args:
            module: Module name to apply.
            force: If True, apply even if tests haven't passed.

        Returns:
            Status message with instructions.
        """
        if module not in self._staged_changes:
            return f"No staged changes for module '{module}'."

        change = self._staged_changes[module]

        # Safety checks
        if not force:
            if not change.test_results:
                return (
                    f"Module '{module}' has not been tested. "
                    "Run test_module() first, or use force=True to apply anyway."
                )
            if not change.last_test_passed():
                return (
                    f"Module '{module}' failed its last test. "
                    "Fix the issues and test again, or use force=True to apply anyway."
                )

        # Verify original hasn't changed on disk
        current_source = self.read_module(module)
        current_hash = hashlib.sha256(current_source.encode()).hexdigest()
        if current_hash != change.original_hash:
            return (
                f"Module '{module}' has been modified on disk since staging. "
                "Please re-read and re-stage your changes."
            )

        # Save current version for rollback
        self._save_version(module, current_source, f"Before applying: {change.description}")

        # Write new source to disk
        module_path = self._source_dir / CORE_MODULES[module]
        try:
            module_path.write_text(change.new_source)
        except Exception as e:
            return f"Failed to write module: {e}"

        # Clean up staged change
        del self._staged_changes[module]

        return (
            f"Module '{module}' updated on disk.\n\n"
            f"IMPORTANT: Changes will take effect after restart.\n"
            f"To restart, exit and re-run the agent.\n\n"
            f"To rollback: core.rollback_to_version('{module}', version_index)"
        )

    def apply_all(self, force: bool = False) -> str:
        """Apply all staged module changes to disk.

        Args:
            force: If True, apply even if tests haven't passed.

        Returns:
            Summary of results.
        """
        if not self._staged_changes:
            return "No staged changes to apply."

        results = []
        modules = list(self._staged_changes.keys())

        for module in modules:
            result = self.apply_module(module, force=force)
            results.append(f"{module}: {result.split(chr(10))[0]}")  # First line only

        return "\n".join(results)

    # =========================================================================
    # Versioning: Save and restore previous versions
    # =========================================================================

    def list_versions(self, module: str) -> str:
        """List saved versions of a module.

        Args:
            module: Module name.

        Returns:
            List of versions with timestamps and descriptions.
        """
        if module not in CORE_MODULES:
            available = ", ".join(CORE_MODULES.keys())
            return f"Unknown module '{module}'. Available: {available}"

        versions = self._version_history.get(module, [])
        if not versions:
            return f"No saved versions for module '{module}'."

        lines = [f"Versions of {module}.py:", ""]
        for i, ver in enumerate(reversed(versions)):  # Most recent first
            dt = datetime.fromtimestamp(ver.timestamp)
            lines.append(f"  [{len(versions) - 1 - i}] {dt.isoformat()} ({ver.hash[:8]})")
            if ver.description:
                lines.append(f"      {ver.description}")

        lines.append("")
        lines.append(f"Use rollback_to_version('{module}', index) to restore.")
        return "\n".join(lines)

    def rollback_to_version(self, module: str, version_index: int) -> str:
        """Rollback a module to a previous version.

        Args:
            module: Module name.
            version_index: Index from list_versions() output.

        Returns:
            Status message.
        """
        if module not in CORE_MODULES:
            available = ", ".join(CORE_MODULES.keys())
            return f"Unknown module '{module}'. Available: {available}"

        versions = self._version_history.get(module, [])
        if not versions:
            return f"No saved versions for module '{module}'."

        if version_index < 0 or version_index >= len(versions):
            return f"Invalid version index. Valid range: 0-{len(versions) - 1}"

        version = versions[version_index]

        # Save current as a new version before rollback
        current = self.read_module(module)
        self._save_version(module, current, "Before rollback")

        # Write the old version
        module_path = self._source_dir / CORE_MODULES[module]
        try:
            module_path.write_text(version.source)
        except Exception as e:
            return f"Failed to write module: {e}"

        return (
            f"Module '{module}' rolled back to version from "
            f"{datetime.fromtimestamp(version.timestamp).isoformat()}.\n"
            f"Restart required for changes to take effect."
        )

    def _save_version(self, module: str, source: str, description: str = "") -> None:
        """Save a version of a module to history.

        Args:
            module: Module name.
            source: Source code to save.
            description: Description of this version.
        """
        version = CoreVersion(
            module=module,
            source=source,
            hash=hashlib.sha256(source.encode()).hexdigest(),
            timestamp=time.time(),
            description=description,
        )

        if module not in self._version_history:
            self._version_history[module] = []

        self._version_history[module].append(version)

        # Persist to disk
        self._save_version_history()

    def _save_version_history(self) -> None:
        """Persist version history to disk."""
        try:
            self._versions_dir.mkdir(parents=True, exist_ok=True)

            for module, versions in self._version_history.items():
                module_dir = self._versions_dir / module
                module_dir.mkdir(exist_ok=True)

                # Save index
                index = []
                for i, ver in enumerate(versions):
                    index.append({
                        "hash": ver.hash,
                        "timestamp": ver.timestamp,
                        "description": ver.description,
                    })
                    # Save source
                    (module_dir / f"{i:04d}_{ver.hash[:8]}.py").write_text(ver.source)

                (module_dir / "index.json").write_text(json.dumps(index, indent=2))

        except Exception:
            pass  # Fail silently on persistence errors

    def _load_version_history(self) -> None:
        """Load version history from disk."""
        try:
            if not self._versions_dir.exists():
                return

            for module_dir in self._versions_dir.iterdir():
                if not module_dir.is_dir():
                    continue

                module = module_dir.name
                index_file = module_dir / "index.json"
                if not index_file.exists():
                    continue

                index = json.loads(index_file.read_text())
                versions = []

                for i, entry in enumerate(index):
                    # Find matching source file
                    source_file = module_dir / f"{i:04d}_{entry['hash'][:8]}.py"
                    if source_file.exists():
                        versions.append(CoreVersion(
                            module=module,
                            source=source_file.read_text(),
                            hash=entry["hash"],
                            timestamp=entry["timestamp"],
                            description=entry.get("description", ""),
                        ))

                if versions:
                    self._version_history[module] = versions

        except Exception:
            pass  # Fail silently on load errors


def subprocess_env() -> dict:
    """Get a clean environment for subprocess testing."""
    import os
    env = os.environ.copy()
    # Remove any paths that might interfere
    env.pop("PYTHONSTARTUP", None)
    return env
