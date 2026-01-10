"""Sandbox module for restricted Python execution.

The sandbox provides a controlled environment where:
- Only explicitly granted capabilities are available
- Dangerous builtins are removed or restricted
- Code execution is isolated from the main process
"""

from agentself.sandbox.sandbox import Sandbox, ExecutionResult

__all__ = ["Sandbox", "ExecutionResult"]
