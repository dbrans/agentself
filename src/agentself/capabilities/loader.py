"""Capability loader - the bootstrapping meta-capability.

The CapabilityLoader is the one capability that always exists in the sandbox.
It's analogous to a kernel: the minimal trusted base that mediates access
to everything else.

The agent uses the loader to:
- Discover what capabilities are available
- View capability contracts before installation
- Install capabilities (with user approval of contracts)
- Uninstall capabilities
- List currently installed capabilities
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Type

from agentself.capabilities.base import Capability

if TYPE_CHECKING:
    from agentself.core import CapabilityContract
    from agentself.sandbox import Sandbox


@dataclass
class CapabilityManifest:
    """Metadata about an available capability."""

    name: str
    """The capability's name (used as the variable name in sandbox)."""

    class_name: str
    """The Python class name."""

    description: str
    """What this capability does."""

    module: str
    """The module path (e.g., 'agentself.capabilities.file_system')."""

    contract_summary: str
    """Human-readable summary of the contract."""

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"


class CapabilityLoader(Capability):
    """Discover and install capabilities into the sandbox.

    This is the one capability that exists from the start—the minimal
    trusted base that mediates access to everything else.

    Example usage in the sandbox:
        >>> loader.list_available()
        ['fs', 'cmd', 'user', 'self']

        >>> loader.describe_available('fs')
        'FileSystemCapability: Read and write files...'

        >>> loader.install('fs', allowed_paths=['/project'])
        <FileSystemCapability(name='fs', methods=5)>

        >>> loader.list_installed()
        ['loader', 'fs']
    """

    name = "loader"
    description = "Discover and install capabilities into the sandbox."

    # Registry of available capabilities
    # In a full implementation, this could be loaded from a manifest file
    # or discovered from a package registry
    BUILTIN_CAPABILITIES: dict[str, tuple[str, Type[Capability]]] = {}

    def __init__(
        self,
        sandbox: "Sandbox | None" = None,
        registry_path: Path | None = None,
    ):
        """Initialize the loader.

        Args:
            sandbox: The sandbox to install capabilities into.
            registry_path: Path to a capability registry file (optional).
        """
        self._sandbox = sandbox
        self._registry_path = registry_path
        self._available: dict[str, CapabilityManifest] = {}
        self._pending_approval: dict[str, tuple[Type[Capability], dict]] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register the built-in capabilities."""
        # Import here to avoid circular dependencies
        from agentself.capabilities.command_line import CommandLineCapability
        from agentself.capabilities.file_system import FileSystemCapability
        from agentself.capabilities.self_source import SelfSourceCapability
        from agentself.capabilities.user_communication import (
            UserCommunicationCapability,
        )

        builtins = [
            ("fs", FileSystemCapability),
            ("cmd", CommandLineCapability),
            ("user", UserCommunicationCapability),
            ("self", SelfSourceCapability),
        ]

        for name, cls in builtins:
            instance = cls() if name != "self" else cls(sandbox=self._sandbox)
            contract = instance.contract()
            self._available[name] = CapabilityManifest(
                name=name,
                class_name=cls.__name__,
                description=cls.description,
                module=cls.__module__,
                contract_summary=str(contract),
            )
            # Store the class for later instantiation
            self.BUILTIN_CAPABILITIES[name] = (cls.__module__, cls)

    def contract(self) -> "CapabilityContract":
        """Declare what this capability might do."""
        from agentself.core import CapabilityContract

        return CapabilityContract(
            reads=["registry:*"],
            spawns=True,  # Can create new capabilities
        )

    # =========================================================================
    # Discovery: What's available?
    # =========================================================================

    def list_available(self) -> list[str]:
        """List all available capability names.

        Returns:
            List of capability names that can be installed.
        """
        return list(self._available.keys())

    def describe_available(self, name: str) -> str:
        """Get detailed description of an available capability.

        Args:
            name: Name of the capability.

        Returns:
            Description including contract summary.
        """
        if name not in self._available:
            return f"Unknown capability: '{name}'"

        manifest = self._available[name]
        lines = [
            f"{manifest.class_name}: {manifest.description}",
            "",
            f"Contract: {manifest.contract_summary}",
        ]
        return "\n".join(lines)

    def get_contract(self, name: str) -> "CapabilityContract | None":
        """Get the contract for an available capability.

        Args:
            name: Name of the capability.

        Returns:
            The capability's contract, or None if not found.
        """
        if name not in self._available:
            return None

        # Instantiate temporarily to get the contract
        if name in self.BUILTIN_CAPABILITIES:
            _, cls = self.BUILTIN_CAPABILITIES[name]
            try:
                instance = cls()
                return instance.contract()
            except Exception:
                return None

        return None

    # =========================================================================
    # Installation: Add capabilities to the sandbox
    # =========================================================================

    def install(self, name: str, **kwargs) -> "Capability | str":
        """Install a capability into the sandbox.

        This creates an instance of the capability and injects it
        into the sandbox's namespace.

        Args:
            name: Name of the capability to install.
            **kwargs: Arguments to pass to the capability's __init__.

        Returns:
            The installed capability instance, or an error message.

        Note:
            In a full implementation, this would require user approval
            of the capability's contract before installation.
        """
        if self._sandbox is None:
            return "Error: Sandbox not connected"

        if name not in self._available:
            return f"Error: Unknown capability '{name}'"

        if name in self._sandbox.capabilities:
            return f"Capability '{name}' is already installed"

        # Get the class
        if name not in self.BUILTIN_CAPABILITIES:
            return f"Error: Capability '{name}' not in registry"

        _, cls = self.BUILTIN_CAPABILITIES[name]

        # Special handling for capabilities that need sandbox reference
        if name == "self":
            kwargs["sandbox"] = self._sandbox

        # Instantiate
        try:
            instance = cls(**kwargs)
        except TypeError as e:
            return f"Error instantiating '{name}': {e}"
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

        # Inject into sandbox
        self._sandbox.inject_capability(name, instance)

        return instance

    def install_derived(
        self,
        name: str,
        from_capability: str,
        **restrictions,
    ) -> "Capability | str":
        """Install a derived (restricted) version of a capability.

        Args:
            name: Name for the new capability in the sandbox.
            from_capability: Name of the installed capability to derive from.
            **restrictions: Restrictions to apply.

        Returns:
            The installed derived capability, or an error message.
        """
        if self._sandbox is None:
            return "Error: Sandbox not connected"

        if from_capability not in self._sandbox.capabilities:
            return f"Error: Capability '{from_capability}' is not installed"

        base = self._sandbox.capabilities[from_capability]
        derived = base.derive(**restrictions)

        self._sandbox.inject_capability(name, derived)
        return derived

    # =========================================================================
    # Management: What's installed?
    # =========================================================================

    def list_installed(self) -> list[str]:
        """List all currently installed capabilities.

        Returns:
            List of installed capability names.
        """
        if self._sandbox is None:
            return []
        return list(self._sandbox.capabilities.keys())

    def uninstall(self, name: str) -> str:
        """Remove a capability from the sandbox.

        Args:
            name: Name of the capability to remove.

        Returns:
            Success or error message.
        """
        if self._sandbox is None:
            return "Error: Sandbox not connected"

        if name == "loader":
            return "Error: Cannot uninstall the loader"

        if name not in self._sandbox.capabilities:
            return f"Capability '{name}' is not installed"

        self._sandbox.remove_capability(name)
        return f"Capability '{name}' uninstalled"

    def describe_installed(self, name: str) -> str:
        """Get description of an installed capability.

        Args:
            name: Name of the installed capability.

        Returns:
            The capability's describe() output.
        """
        if self._sandbox is None:
            return "Error: Sandbox not connected"

        if name not in self._sandbox.capabilities:
            return f"Capability '{name}' is not installed"

        return self._sandbox.capabilities[name].describe()

    # =========================================================================
    # Registry management (for future extension)
    # =========================================================================

    def register(
        self,
        name: str,
        capability_class: Type[Capability],
        module: str | None = None,
    ) -> str:
        """Register a new capability in the local registry.

        Args:
            name: Name for the capability.
            capability_class: The capability class.
            module: Module path (optional, inferred if not provided).

        Returns:
            Success or error message.
        """
        if name in self._available:
            return f"Capability '{name}' is already registered"

        try:
            instance = capability_class()
            contract = instance.contract()
        except Exception as e:
            return f"Error: Could not instantiate for registration: {e}"

        self._available[name] = CapabilityManifest(
            name=name,
            class_name=capability_class.__name__,
            description=capability_class.description,
            module=module or capability_class.__module__,
            contract_summary=str(contract),
        )
        self.BUILTIN_CAPABILITIES[name] = (
            module or capability_class.__module__,
            capability_class,
        )

        return f"Registered capability '{name}'"
