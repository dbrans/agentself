"""Self-source capability for agent introspection and self-modification.

Allows the agent to read its own source code, list capabilities,
and potentially create new capabilities.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentself.capabilities.base import Capability

if TYPE_CHECKING:
    from agentself.sandbox import Sandbox


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
        self._staged_capabilities: dict[str, str] = {}
    
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
            return inspect.getsource(type(cap))
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
        
        self._staged_capabilities[name] = code
        return f"Capability '{name}' staged. Use commit_capability() to persist."
    
    def get_staged_capabilities(self) -> dict[str, str]:
        """Get all staged (uncommitted) capabilities.
        
        Returns:
            Dict of capability name to source code.
        """
        return dict(self._staged_capabilities)
    
    def commit_capability(self, name: str) -> str:
        """Commit a staged capability to disk.
        
        Args:
            name: Name of the staged capability to commit.
            
        Returns:
            Status message with file path.
        """
        if name not in self._staged_capabilities:
            return f"No staged capability named '{name}'."
        
        code = self._staged_capabilities[name]
        
        # Write to capabilities directory
        cap_dir = self._source_dir / "capabilities"
        cap_file = cap_dir / f"{name}.py"
        
        try:
            cap_dir.mkdir(parents=True, exist_ok=True)
            cap_file.write_text(code)
            del self._staged_capabilities[name]
            return f"Capability '{name}' written to {cap_file}"
        except Exception as e:
            return f"Error writing capability: {e}"
