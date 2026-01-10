"""Self-source capability for agent introspection and self-modification.

Allows the agent to read its own source code, list capabilities,
create new capabilities, and modify existing ones.
"""

from __future__ import annotations

import difflib
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentself.capabilities.base import Capability

if TYPE_CHECKING:
    from agentself.sandbox import Sandbox


@dataclass
class CapabilityChange:
    """Represents a change to a capability."""
    name: str
    original_source: str | None  # None for new capabilities
    new_source: str
    is_new: bool = False
    
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


class SelfSourceCapability(Capability):
    """Read and modify the agent's own source and capabilities."""
    
    name = "self"
    description = "Inspect and modify the agent's source code and capabilities."
    
    def __init__(self, sandbox: "Sandbox | None" = None, source_dir: Path | None = None):
        """Initialize with reference to the sandbox.
        
        Args:
            sandbox: The sandbox this capability is part of (for capability listing).
            source_dir: Directory containing agent source files.
        """
        self._sandbox = sandbox
        self._source_dir = source_dir or Path("src/agentself")
        self._staged_capabilities: dict[str, CapabilityChange] = {}
        self._original_sources: dict[str, str] = {}  # Cache of original sources
    
    def list_capabilities(self) -> list[str]:
        """List all capabilities currently available in the sandbox.
        
        Returns:
            List of capability names.
        """
        if self._sandbox is None:
            return ["(sandbox not connected)"]
        return list(self._sandbox.capabilities.keys())
    
    def describe_capability(self, name: str) -> str:
        """Get the description of a specific capability.
        
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
        """Read the main agent source code.
        
        Returns:
            The agent.py source code.
        """
        agent_file = self._source_dir / "agent.py"
        if agent_file.exists():
            return agent_file.read_text()
        return f"Agent source not found at {agent_file}"
    
    def add_capability(self, name: str, code: str) -> str:
        """Stage a new capability for creation.
        
        The capability code should define a class that inherits from Capability.
        
        Args:
            name: Name for the new capability.
            code: Python source code defining the capability class.
            
        Returns:
            Status message.
        """
        # Validate the code compiles
        try:
            compile(code, f"<capability:{name}>", "exec")
        except SyntaxError as e:
            return f"Syntax error in capability code: {e}"
        
        # Check it looks like a capability class
        if "class " not in code or "Capability" not in code:
            return "Code must define a class that inherits from Capability."
        
        self._staged_capabilities[name] = CapabilityChange(
            name=name,
            original_source=None,
            new_source=code,
            is_new=True,
        )
        return f"Capability '{name}' staged. Use commit_capability() to persist."
    
    def modify_capability(self, name: str, new_code: str) -> str:
        """Stage modifications to an existing capability.
        
        Args:
            name: Name of the capability to modify.
            new_code: New Python source code for the capability.
            
        Returns:
            Status message.
        """
        # Validate the code compiles
        try:
            compile(new_code, f"<capability:{name}>", "exec")
        except SyntaxError as e:
            return f"Syntax error in capability code: {e}"
        
        # Get original source
        original = self._original_sources.get(name)
        if original is None:
            # Try to read it
            source = self.read_capability_source(name)
            if "not found" in source.lower() or "could not" in source.lower():
                return f"Cannot modify '{name}': capability not found."
            original = source
        
        self._staged_capabilities[name] = CapabilityChange(
            name=name,
            original_source=original,
            new_source=new_code,
            is_new=False,
        )
        return f"Capability '{name}' modified. Use diff_capability() to review, commit_capability() to persist."
    
    def diff_capability(self, name: str) -> str:
        """Show the diff for a staged capability change.
        
        Args:
            name: Name of the capability to diff.
            
        Returns:
            Unified diff of the changes, or error message.
        """
        if name not in self._staged_capabilities:
            return f"No staged changes for capability '{name}'."
        
        change = self._staged_capabilities[name]
        return change.get_diff()
    
    def track_changes(self) -> str:
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
                lines.append(f"  + {change.name}")
        
        if modified_caps:
            lines.append("Modified Capabilities:")
            for change in modified_caps:
                lines.append(f"  ~ {change.name}")
        
        lines.append("")
        lines.append(f"Total: {len(self._staged_capabilities)} staged change(s)")
        lines.append("Use diff_capability(name) to see details, commit_capability(name) to persist.")
        
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
            cap_file.write_text(change.new_source)
            
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

