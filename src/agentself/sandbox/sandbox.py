"""Sandbox execution environment with restricted globals.

The Sandbox provides a locked-down Python REPL where:
- Capabilities are injected as objects
- Dangerous builtins (open, exec, eval, __import__) are removed
- Safe builtins (print, len, range, etc.) are available
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass, field
from io import StringIO
from typing import Any, TYPE_CHECKING

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
    "print": print,  # Will be redirected
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
    
    # Constants
    "True": True,
    "False": False,
    "None": None,
}


@dataclass
class ExecutionResult:
    """Result of sandbox code execution."""
    
    success: bool
    output: str = ""
    error: str = ""
    return_value: Any = None
    
    def __str__(self) -> str:
        """Format as readable output."""
        if self.success:
            parts = []
            if self.output:
                parts.append(self.output)
            if self.return_value is not None:
                parts.append(f"=> {repr(self.return_value)}")
            return "\n".join(parts) if parts else "(no output)"
        else:
            return f"Error: {self.error}"


class Sandbox:
    """A restricted Python execution environment."""
    
    def __init__(self, capabilities: dict[str, "Capability"] | None = None):
        """Initialize sandbox with optional capabilities.
        
        Args:
            capabilities: Dict of name -> Capability to inject.
        """
        self.capabilities: dict[str, "Capability"] = capabilities or {}
        self._globals: dict[str, Any] = {}
        self._locals: dict[str, Any] = {}
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
    
    def execute(self, code: str) -> ExecutionResult:
        """Execute code in the sandbox.
        
        Args:
            code: Python code to execute.
            
        Returns:
            ExecutionResult with success status, output, and return value.
        """
        # Capture stdout
        old_stdout = sys.stdout
        captured_output = StringIO()
        
        try:
            sys.stdout = captured_output
            
            # Try to evaluate as expression first (for return value)
            try:
                result = eval(code, self._globals, self._locals)
                return ExecutionResult(
                    success=True,
                    output=captured_output.getvalue(),
                    return_value=result,
                )
            except SyntaxError:
                # Not an expression, execute as statements
                exec(code, self._globals, self._locals)
                return ExecutionResult(
                    success=True,
                    output=captured_output.getvalue(),
                )
        
        except Exception as e:
            # Get the formatted traceback
            tb = traceback.format_exc()
            return ExecutionResult(
                success=False,
                output=captured_output.getvalue(),
                error=f"{type(e).__name__}: {e}\n{tb}",
            )
        
        finally:
            sys.stdout = old_stdout
    
    def execute_multi(self, statements: list[str]) -> list[ExecutionResult]:
        """Execute multiple statements in sequence.
        
        Args:
            statements: List of Python statements to execute.
            
        Returns:
            List of ExecutionResults, one per statement.
        """
        results = []
        for stmt in statements:
            result = self.execute(stmt)
            results.append(result)
            if not result.success:
                # Stop on first error
                break
        return results
    
    def get_variable(self, name: str) -> Any:
        """Get a variable from the sandbox's local namespace.
        
        Args:
            name: Variable name.
            
        Returns:
            The variable's value.
            
        Raises:
            KeyError: If variable not found.
        """
        if name in self._locals:
            return self._locals[name]
        if name in self._globals:
            return self._globals[name]
        raise KeyError(f"Variable '{name}' not found in sandbox")
    
    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable in the sandbox's local namespace.
        
        Args:
            name: Variable name.
            value: Value to set.
        """
        self._locals[name] = value
    
    def reset(self) -> None:
        """Reset the sandbox state (clear locals, keep capabilities)."""
        self._locals = {}
        self._rebuild_globals()
    
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
                lines.append(f"  - {name}: {type(value).__name__}")
        else:
            lines.append("  (none)")
        
        return "\n".join(lines)
