"""Capabilities module for the sandboxed agent.

Capabilities are objects injected into the sandbox that provide controlled access
to external resources (files, network, shell, etc). Each capability:
- Has a self-documenting interface via describe()
- Can be scoped (e.g., file access limited to specific paths)
- Can be revoked by removing from the sandbox
"""

from agentself.capabilities.base import Capability
from agentself.capabilities.file_system import FileSystemCapability
from agentself.capabilities.user_communication import UserCommunicationCapability
from agentself.capabilities.self_source import SelfSourceCapability
from agentself.capabilities.command_line import CommandLineCapability

__all__ = [
    "Capability",
    "FileSystemCapability",
    "UserCommunicationCapability",
    "SelfSourceCapability",
    "CommandLineCapability",
]
