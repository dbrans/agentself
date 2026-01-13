"""Capabilities module for the agent framework.

Capabilities are objects that provide controlled access to external resources
(files, shell, etc). Each capability:
- Has a self-documenting interface via describe()
- Declares its potential effects via contract()
- Can be scoped via derive() to create restricted versions

Current capabilities:
- FileSystemCapability: Scoped file read/write access
- CommandLineCapability: Shell command execution with optional allowlist

Archived capabilities (in agentself._archive.capabilities):
- SelfSourceCapability: Runtime capability introspection and modification
- CoreSourceCapability: Core infrastructure modification
- UserCommunicationCapability: Async user communication
- CapabilityLoader: Meta-capability for discovering capabilities
"""

from agentself.capabilities.base import Capability
from agentself.capabilities.command_line import CommandLineCapability
from agentself.capabilities.file_system import FileSystemCapability
from agentself.capabilities.skills import SkillsCapability

__all__ = [
    "Capability",
    "CommandLineCapability",
    "FileSystemCapability",
    "SkillsCapability",
]
