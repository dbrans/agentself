"""Capabilities module for the sandboxed agent.

Capabilities are objects injected into the sandbox that provide controlled access
to external resources (files, network, shell, etc). Each capability:
- Has a self-documenting interface via describe()
- Declares its potential effects via contract()
- Can be scoped via derive() to create restricted versions
- Can be revoked by removing from the sandbox

Key classes:
- Capability: Base class for all capabilities
- CapabilityLoader: Meta-capability for discovering and installing others
- FileSystemCapability: File read/write access
- CommandLineCapability: Shell command execution
- UserCommunicationCapability: Interaction with the user
- SelfSourceCapability: Introspection and self-modification (Layer 2: capabilities)
- CoreSourceCapability: Core infrastructure modification (Layer 1: agent/sandbox/etc)
"""

from agentself.capabilities.base import Capability
from agentself.capabilities.command_line import CommandLineCapability
from agentself.capabilities.core_source import CoreSourceCapability
from agentself.capabilities.file_system import FileSystemCapability
from agentself.capabilities.loader import CapabilityLoader, CapabilityManifest
from agentself.capabilities.self_source import SelfSourceCapability
from agentself.capabilities.user_communication import UserCommunicationCapability

__all__ = [
    "Capability",
    "CapabilityLoader",
    "CapabilityManifest",
    "CommandLineCapability",
    "CoreSourceCapability",
    "FileSystemCapability",
    "SelfSourceCapability",
    "UserCommunicationCapability",
]
