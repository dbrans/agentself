"""agentself - A self-improving sandboxed coding agent."""

from agentself.agent import SandboxedAgent, Message
from agentself.sandbox import Sandbox, ExecutionResult
from agentself.capabilities import (
    Capability,
    FileSystemCapability,
    UserCommunicationCapability,
    SelfSourceCapability,
    CommandLineCapability,
)

__all__ = [
    # Agent
    "SandboxedAgent",
    "Message",
    # Sandbox
    "Sandbox",
    "ExecutionResult",
    # Capabilities
    "Capability",
    "FileSystemCapability",
    "UserCommunicationCapability",
    "SelfSourceCapability",
    "CommandLineCapability",
]
