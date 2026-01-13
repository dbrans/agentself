"""Shared runtime objects for the REPL harness."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any, Callable

from agentself.harness.hub import MCPHub
from agentself.harness.repl import REPLSubprocess
from agentself.harness.state import StateManager


@dataclass
class HarnessRuntime:
    """Shared state for the MCP server and attach server."""

    repl: REPLSubprocess
    hub: MCPHub
    state_manager: StateManager
    lock: threading.Lock
    relay_handler: Callable[[str, str, dict], Any]

    def acquire(self, wait: bool = True, timeout: float | None = None) -> bool:
        """Acquire the runtime lock."""
        if not wait:
            return self.lock.acquire(blocking=False)
        if timeout is None:
            return self.lock.acquire()
        return self.lock.acquire(timeout=timeout)

    def release(self) -> None:
        """Release the runtime lock."""
        if self.lock.locked():
            self.lock.release()

    def busy(self) -> bool:
        """Return True if the REPL is currently in use."""
        return self.lock.locked()

    async def aclose(self) -> None:
        """Async cleanup for the runtime."""
        await self.hub.close()
        self.repl.close()

    def close(self) -> None:
        """Sync cleanup for the runtime."""
        try:
            asyncio.run(self.aclose())
        except RuntimeError:
            # If a loop is already running, do best-effort sync cleanup.
            self.repl.close()


_runtime: HarnessRuntime | None = None


def create_runtime() -> HarnessRuntime:
    """Create a new runtime with shared REPL, hub, and state manager."""
    hub = MCPHub()
    state_manager = StateManager()
    lock = threading.Lock()

    def relay_handler(capability: str, method: str, kwargs: dict) -> Any:
        """Handle relay calls from the REPL by forwarding to MCP hub."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(hub.call(capability, method, kwargs))
        finally:
            loop.close()

    repl = REPLSubprocess(relay_handler=relay_handler)
    return HarnessRuntime(
        repl=repl,
        hub=hub,
        state_manager=state_manager,
        lock=lock,
        relay_handler=relay_handler,
    )


def get_runtime() -> HarnessRuntime:
    """Get or create the global runtime."""
    global _runtime
    if _runtime is None:
        _runtime = create_runtime()
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (primarily for tests)."""
    global _runtime
    if _runtime is not None:
        _runtime.close()
    _runtime = None
