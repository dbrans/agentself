"""AgentSelf: A capability-based self-improving agent framework.

This package provides:
- A sandboxed execution environment with two-phase execution
- A capability system for controlled access to external resources
- Capability contracts for declaring potential side effects
- Permission handling for human-in-the-loop oversight
- Self-modification capabilities for runtime agent improvement
- A capability loader for discovering and installing capabilities

Key Components:
- Sandbox: Restricted Python execution with capability injection
- Capability: Base class for controlled resource access
- CapabilityContract: Declares what a capability might do
- CapabilityLoader: Meta-capability for installing other capabilities
- SandboxedAgent: LLM-powered agent with code execution
- Permission handlers: Auto-approve, interactive, policy-based

Example:
    from agentself import SandboxedAgent

    agent = SandboxedAgent()
    response = agent.chat("List all Python files in the current directory")
    print(response)
"""

from agentself.agent import (
    AgentConfig,
    ConversationTurn,
    Message,
    SandboxedAgent,
)
from agentself.capabilities import (
    Capability,
    CapabilityLoader,
    CapabilityManifest,
    CommandLineCapability,
    FileSystemCapability,
    SelfSourceCapability,
    UserCommunicationCapability,
)
from agentself.core import (
    CapabilityCall,
    CapabilityContract,
    DependencyInfo,
    ExecutionMode,
    ExecutionPlan,
    ExecutionResult,
    PermissionStrategy,
)
from agentself.permissions import (
    AutoApproveHandler,
    AutoDenyHandler,
    CompositeHandler,
    InteractiveHandler,
    PermissionDecision,
    PermissionHandler,
    PermissionRequest,
    PermissionRule,
    PolicyHandler,
)
from agentself.proxy import (
    CallRecorder,
    CapabilityProxy,
    ProxyFactory,
)
from agentself.sandbox import (
    Sandbox,
    SAFE_BUILTINS,
)

__version__ = "0.1.0"

__all__ = [
    # Agent
    "SandboxedAgent",
    "AgentConfig",
    "Message",
    "ConversationTurn",
    # Sandbox
    "Sandbox",
    "SAFE_BUILTINS",
    # Core types
    "CapabilityCall",
    "CapabilityContract",
    "ExecutionPlan",
    "ExecutionResult",
    "ExecutionMode",
    "PermissionStrategy",
    "DependencyInfo",
    # Capabilities
    "Capability",
    "CapabilityLoader",
    "CapabilityManifest",
    "FileSystemCapability",
    "CommandLineCapability",
    "UserCommunicationCapability",
    "SelfSourceCapability",
    # Permissions
    "PermissionHandler",
    "PermissionRequest",
    "PermissionDecision",
    "PermissionRule",
    "AutoApproveHandler",
    "AutoDenyHandler",
    "InteractiveHandler",
    "PolicyHandler",
    "CompositeHandler",
    # Proxy
    "CapabilityProxy",
    "CallRecorder",
    "ProxyFactory",
]
