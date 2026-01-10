"""Base class for all capabilities.

A Capability is an object that provides controlled access to external resources.
Capabilities are injected into the sandbox and can be introspected by the agent.

Key concepts:
- Capabilities are runtime objects in the agent's memory
- Each capability has a contract() declaring what it might do
- Capabilities can be derived to create restricted versions
- Capabilities self-document via describe()
"""

from __future__ import annotations

import copy
import inspect
from abc import ABC
from typing import Any, Callable, TYPE_CHECKING, get_type_hints

if TYPE_CHECKING:
    from agentself.core import CapabilityContract, PermissionStrategy


class Capability(ABC):
    """Base class for all capabilities.

    A capability is a runtime object that provides controlled access to
    external resources. Unlike MCP tools (remote procedures) or Claude Skills
    (prompt templates), capabilities are stateful, composable, and revocable.

    Subclasses should:
    - Set `name` and `description` class attributes
    - Override `contract()` to declare what the capability might do
    - Implement methods that provide the capability's functionality
    - Each method should have a docstring (used for self-documentation)

    Example:
        class FileCapability(Capability):
            name = "fs"
            description = "Read and write files."

            def contract(self) -> CapabilityContract:
                return CapabilityContract(
                    reads=["file:*"],
                    writes=["file:*"],
                )

            def read(self, path: str) -> str:
                '''Read file contents.'''
                return Path(path).read_text()
    """

    name: str = "unnamed_capability"
    description: str = "A capability."

    # Default permission strategy for this capability
    # Can be overridden per-instance
    default_strategy: "PermissionStrategy | None" = None

    def contract(self) -> "CapabilityContract":
        """Declare what side effects this capability might produce.

        The contract enables contract-based approval: users approve what
        the capability *can* do upfront, rather than approving each call.

        Returns:
            CapabilityContract describing potential reads, writes, executes, etc.

        Override this in subclasses to declare the capability's contract.
        The base implementation returns an empty contract (no declared effects).
        """
        # Import here to avoid circular dependency
        from agentself.core import CapabilityContract

        return CapabilityContract()

    def derive(self, **restrictions) -> "Capability":
        """Create a more restricted version of this capability.

        This enables capability composition and delegation: you can pass
        a derived capability with fewer permissions to sub-agents.

        Args:
            **restrictions: Restriction parameters specific to the capability.
                Common patterns:
                - read_only=True: Disable write operations
                - allowed_paths=[...]: Restrict to specific paths
                - allowed_commands=[...]: Restrict to specific commands

        Returns:
            A new capability instance with the restrictions applied.

        The base implementation creates a shallow copy with restrictions
        stored. Subclasses should override to apply restrictions properly.
        """
        derived = copy.copy(self)
        derived._restrictions = restrictions
        return derived

    def describe(self) -> str:
        """Return a self-documenting description of this capability.

        Lists all public methods with their signatures and docstrings,
        plus the capability's contract.
        """
        lines = [f"{self.name}: {self.description}", ""]

        # Show contract
        contract = self.contract()
        if str(contract) != "(no effects declared)":
            lines.append(f"Contract: {contract}")
            lines.append("")

        lines.append("Methods:")

        for method_name in dir(self):
            if method_name.startswith("_"):
                continue

            method = getattr(self, method_name)
            if not callable(method):
                continue

            # Skip base class methods in the listing
            if method_name in ("describe", "contract", "derive"):
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
        method_count = len(self._get_methods()) - 3  # Exclude describe, contract, derive
        return f"<{self.__class__.__name__}(name='{self.name}', methods={method_count})>"

    def __str__(self) -> str:
        """Show the describe() output when converted to string."""
        return self.describe()
