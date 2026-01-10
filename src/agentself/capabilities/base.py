"""Base class for all capabilities.

A Capability is an object that provides controlled access to external resources.
Capabilities are injected into the sandbox and can be introspected by the agent.
"""

from __future__ import annotations

import inspect
from abc import ABC
from typing import Any, Callable, get_type_hints


class Capability(ABC):
    """Base class for all capabilities.
    
    Subclasses should:
    - Set `name` and `description` class attributes
    - Implement methods that provide the capability's functionality
    - Each method should have a docstring (used for self-documentation)
    """
    
    name: str = "unnamed_capability"
    description: str = "A capability."
    
    def describe(self) -> str:
        """Return a self-documenting description of this capability.
        
        Lists all public methods with their signatures and docstrings.
        """
        lines = [f"{self.name}: {self.description}", ""]
        lines.append("Methods:")
        
        for method_name in dir(self):
            if method_name.startswith("_"):
                continue
            
            method = getattr(self, method_name)
            if not callable(method):
                continue
            
            # Get the signature
            try:
                sig = inspect.signature(method)
                sig_str = f"{method_name}{sig}"
            except (ValueError, TypeError):
                sig_str = f"{method_name}(...)"
            
            # Get the docstring (first line only)
            doc = method.__doc__ or "No description."
            doc_first_line = doc.strip().split("\n")[0]
            
            lines.append(f"  - {sig_str}")
            lines.append(f"      {doc_first_line}")
        
        return "\n".join(lines)
    
    def _get_methods(self) -> dict[str, Callable]:
        """Get all public methods of this capability."""
        methods = {}
        for method_name in dir(self):
            if method_name.startswith("_"):
                continue
            method = getattr(self, method_name)
            if callable(method):
                methods[method_name] = method
        return methods
    
    def __repr__(self) -> str:
        """Show useful info when printed in REPL."""
        method_count = len(self._get_methods())
        return f"<{self.__class__.__name__}(name='{self.name}', methods={method_count})>"
    
    def __str__(self) -> str:
        """Show the describe() output when converted to string."""
        return self.describe()
