"""Sandbox execution environment with two-phase execution.

The Sandbox provides a restricted Python environment where:
1. Capabilities are injected as objects (the only way to access external resources)
2. Code is first analyzed in RECORD mode to see what it will do
3. Permission is requested from the handler
4. Only if approved, code executes in EXECUTE mode with real capabilities

This two-phase model enables:
- Human-in-the-loop approval
- Automatic policy enforcement
- Understanding code intent before side effects
"""

from __future__ import annotations

import ast
import sys
import traceback
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, TYPE_CHECKING

from agentself.core import (
    CapabilityCall,
    DependencyInfo,
    ExecutionMode,
    ExecutionPlan,
    ExecutionResult,
)
from agentself.permissions import (
    AutoApproveHandler,
    PermissionDecision,
    PermissionHandler,
    PermissionRequest,
)
from agentself.proxy import CallRecorder, ProxyFactory

if TYPE_CHECKING:
    from agentself.capabilities.base import Capability


# Safe builtins that don't provide system access
SAFE_BUILTINS = {
    # Types
    "bool": bool,
    "int": int,
    "float": float,
    "str": str,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "frozenset": frozenset,
    "bytes": bytes,
    "bytearray": bytearray,
    "type": type,
    "object": object,
    # Functions
    "abs": abs,
    "all": all,
    "any": any,
    "bin": bin,
    "callable": callable,
    "chr": chr,
    "dir": dir,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "format": format,
    "getattr": getattr,
    "hasattr": hasattr,
    "hash": hash,
    "hex": hex,
    "id": id,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,  # Will be redirected during execution
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "setattr": setattr,
    "slice": slice,
    "sorted": sorted,
    "sum": sum,
    "zip": zip,
    # Exceptions (for try/except)
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "AttributeError": AttributeError,
    "RuntimeError": RuntimeError,
    "StopIteration": StopIteration,
    "PermissionError": PermissionError,
    "FileNotFoundError": FileNotFoundError,
    "OSError": OSError,
    # Constants
    "True": True,
    "False": False,
    "None": None,
}


class VariableTracker(ast.NodeVisitor):
    """AST visitor to track variable reads and writes."""

    def __init__(self):
        self.reads: set[str] = set()
        self.writes: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.reads.add(node.id)
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            self.writes.add(node.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.writes.add(node.name)
        # Don't visit the function body - those are local variables
        for decorator in node.decorator_list:
            self.visit(decorator)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.writes.add(node.name)
        for decorator in node.decorator_list:
            self.visit(decorator)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.writes.add(node.name)
        for base in node.bases:
            self.visit(base)
        for decorator in node.decorator_list:
            self.visit(decorator)


def analyze_variables(code: str) -> tuple[set[str], set[str]]:
    """Analyze code to find variables read and written.

    Returns:
        Tuple of (variables_read, variables_written)
    """
    try:
        tree = ast.parse(code)
        tracker = VariableTracker()
        tracker.visit(tree)
        # Variables that are read before being written are true dependencies
        true_reads = tracker.reads - tracker.writes
        return true_reads, tracker.writes
    except SyntaxError:
        return set(), set()


class Sandbox:
    """A restricted Python execution environment with two-phase execution.

    The sandbox:
    1. Maintains a restricted global namespace with only safe builtins
    2. Injects capabilities as the only way to access external resources
    3. Analyzes code in RECORD mode before executing
    4. Requests permission from the handler before real execution
    5. Tracks dependencies between code blocks
    """

    def __init__(
        self,
        capabilities: dict[str, "Capability"] | None = None,
        permission_handler: PermissionHandler | None = None,
    ):
        """Initialize sandbox.

        Args:
            capabilities: Dict of name -> Capability to inject.
            permission_handler: Handler for permission checks. Defaults to AutoApprove.
        """
        self.capabilities: dict[str, "Capability"] = capabilities or {}
        self.permission_handler = permission_handler or AutoApproveHandler()
        self._globals: dict[str, Any] = {}
        self._locals: dict[str, Any] = {}
        self._block_index = 0
        self._dependencies = DependencyInfo()
        self._execution_history: list[ExecutionResult] = []
        self._rebuild_globals()

    def _rebuild_globals(self) -> None:
        """Rebuild the restricted globals with current capabilities."""
        self._globals = {
            "__builtins__": SAFE_BUILTINS.copy(),
            "__name__": "__sandbox__",
        }

        # Inject capabilities
        for name, cap in self.capabilities.items():
            self._globals[name] = cap

        # Also expose a caps dict for discovery
        self._globals["caps"] = dict(self.capabilities)

    def inject_capability(self, name: str, cap: "Capability") -> None:
        """Add a capability to the sandbox.

        Args:
            name: Name to use in the sandbox (e.g., 'fs' for file system).
            cap: The capability instance.
        """
        self.capabilities[name] = cap
        self._rebuild_globals()

        # Connect SelfSourceCapability to this sandbox if applicable
        if hasattr(cap, "_sandbox"):
            cap._sandbox = self

    def remove_capability(self, name: str) -> bool:
        """Remove a capability from the sandbox.

        Args:
            name: Name of the capability to remove.

        Returns:
            True if removed, False if not found.
        """
        if name in self.capabilities:
            del self.capabilities[name]
            self._rebuild_globals()
            return True
        return False

    def analyze(self, code: str) -> ExecutionPlan:
        """Analyze code to see what it will do (RECORD mode).

        Executes with proxy capabilities that record calls without
        side effects.

        Args:
            code: Python code to analyze.

        Returns:
            ExecutionPlan showing what the code intends to do.
        """
        # Analyze variable usage statically
        vars_read, vars_written = analyze_variables(code)

        # Create proxies for recording
        recorder = CallRecorder()
        factory = ProxyFactory(recorder)

        proxied_globals = {
            "__builtins__": SAFE_BUILTINS.copy(),
            "__name__": "__sandbox__",
        }
        proxied_globals.update(factory.create_proxies(self.capabilities))
        proxied_globals["caps"] = dict(factory.create_proxies(self.capabilities))

        # Include current local variables for context
        proxied_locals = self._locals.copy()

        # Capture stdout during analysis
        old_stdout = sys.stdout
        captured_output = StringIO()

        try:
            sys.stdout = captured_output

            # Try to evaluate as expression first
            try:
                compile(code, "<analyze>", "eval")
                eval(code, proxied_globals, proxied_locals)
            except SyntaxError:
                # Execute as statements
                exec(code, proxied_globals, proxied_locals)

            return ExecutionPlan(
                code=code,
                calls=recorder.calls,
                success=True,
                variables_accessed=vars_read,
                variables_defined=vars_written,
            )

        except Exception as e:
            return ExecutionPlan(
                code=code,
                calls=recorder.calls,
                success=False,
                error=f"{type(e).__name__}: {e}",
                variables_accessed=vars_read,
                variables_defined=vars_written,
            )

        finally:
            sys.stdout = old_stdout

    def execute(
        self,
        code: str,
        skip_permission: bool = False,
        context: dict = None,
    ) -> ExecutionResult:
        """Execute code with two-phase permission checking.

        1. Analyze in RECORD mode to see what will happen
        2. Request permission from the handler
        3. If approved, execute with real capabilities

        Args:
            code: Python code to execute.
            skip_permission: If True, skip permission check (use carefully!).
            context: Additional context to pass to permission handler.

        Returns:
            ExecutionResult with success status, output, and recorded calls.
        """
        # Phase 1: Analyze
        plan = self.analyze(code)

        if not plan.success:
            return ExecutionResult(
                success=False,
                error=plan.error,
                plan=plan,
            )

        # Phase 2: Permission check
        if not skip_permission and plan.calls:
            request = PermissionRequest(plan=plan, context=context or {})
            decision = self.permission_handler.check(request)

            if decision == PermissionDecision.DENY:
                return ExecutionResult(
                    success=False,
                    error=f"Permission denied for: {', '.join(str(c) for c in plan.calls)}",
                    permission_denied=True,
                    plan=plan,
                )

        # Phase 3: Execute for real
        result = self._execute_real(code, plan)

        # Track dependencies
        if result.success:
            self._dependencies.record_block(self._block_index, plan)
            self._block_index += 1
            self._execution_history.append(result)

        return result

    def _execute_real(self, code: str, plan: ExecutionPlan) -> ExecutionResult:
        """Execute code with real capabilities.

        Args:
            code: Python code to execute.
            plan: The pre-analyzed plan.

        Returns:
            ExecutionResult with output and any return value.
        """
        old_stdout = sys.stdout
        captured_output = StringIO()

        # Create a recorder to track actual calls
        recorder = CallRecorder()

        # Wrap capabilities to record actual calls
        wrapped_globals = self._globals.copy()
        for name, cap in self.capabilities.items():
            wrapped_globals[name] = _RecordingCapability(cap, name, recorder)
        wrapped_globals["caps"] = {
            name: _RecordingCapability(cap, name, recorder)
            for name, cap in self.capabilities.items()
        }

        try:
            sys.stdout = captured_output

            # Try to evaluate as expression first (for return value)
            try:
                result = eval(code, wrapped_globals, self._locals)
                return ExecutionResult(
                    success=True,
                    output=captured_output.getvalue(),
                    return_value=result,
                    calls=recorder.calls,
                    plan=plan,
                )
            except SyntaxError:
                # Execute as statements
                exec(code, wrapped_globals, self._locals)
                return ExecutionResult(
                    success=True,
                    output=captured_output.getvalue(),
                    calls=recorder.calls,
                    plan=plan,
                )

        except Exception as e:
            tb = traceback.format_exc()
            return ExecutionResult(
                success=False,
                output=captured_output.getvalue(),
                error=f"{type(e).__name__}: {e}\n{tb}",
                calls=recorder.calls,
                plan=plan,
            )

        finally:
            sys.stdout = old_stdout

    def execute_unchecked(self, code: str) -> ExecutionResult:
        """Execute code without permission checking.

        Use only for trusted code (e.g., initialization).
        """
        return self.execute(code, skip_permission=True)

    def get_variable(self, name: str) -> Any:
        """Get a variable from the sandbox's local namespace."""
        if name in self._locals:
            return self._locals[name]
        if name in self._globals:
            return self._globals[name]
        raise KeyError(f"Variable '{name}' not found in sandbox")

    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable in the sandbox's local namespace."""
        self._locals[name] = value

    def reset(self) -> None:
        """Reset the sandbox state (clear locals, keep capabilities)."""
        self._locals = {}
        self._block_index = 0
        self._dependencies = DependencyInfo()
        self._execution_history = []
        self._rebuild_globals()

    def get_dependencies(self) -> DependencyInfo:
        """Get the dependency tracking information."""
        return self._dependencies

    def get_history(self) -> list[ExecutionResult]:
        """Get the execution history."""
        return self._execution_history.copy()

    def describe(self) -> str:
        """Get a description of the sandbox's current state."""
        lines = ["Sandbox State:", ""]

        lines.append("Capabilities:")
        if self.capabilities:
            for name, cap in self.capabilities.items():
                lines.append(f"  - {name}: {cap.description}")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append("Variables:")
        if self._locals:
            for name, value in self._locals.items():
                val_repr = repr(value)
                if len(val_repr) > 50:
                    val_repr = val_repr[:47] + "..."
                lines.append(f"  - {name}: {type(value).__name__} = {val_repr}")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(f"Execution history: {len(self._execution_history)} block(s)")

        return "\n".join(lines)


class _RecordingCapability:
    """Wrapper that records actual capability calls during execution.

    Unlike CapabilityProxy (which doesn't execute), this calls through
    to the real capability while recording what was called.
    """

    def __init__(self, capability: "Capability", name: str, recorder: CallRecorder):
        self._capability = capability
        self._name = name
        self._recorder = recorder

    def __getattr__(self, attr_name: str) -> Any:
        attr = getattr(self._capability, attr_name)
        if callable(attr) and not attr_name.startswith("_"):
            return self._wrap_method(attr_name, attr)
        return attr

    def _wrap_method(self, method_name: str, method):
        def wrapper(*args, **kwargs):
            self._recorder.record(self._name, method_name, args, kwargs)
            return method(*args, **kwargs)

        return wrapper

    def __repr__(self) -> str:
        return repr(self._capability)
