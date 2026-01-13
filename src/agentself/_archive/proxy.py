"""Capability proxying for two-phase execution.

The proxy layer enables "record mode" where we can see what capabilities
the code intends to use without actually executing them. This is the
foundation of the permission system.

Key classes:
- CallRecorder: Collects capability calls during record mode
- CapabilityProxy: Wraps a capability to intercept and record calls
- ProxyFactory: Creates proxied versions of capability dictionaries
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, get_type_hints, TYPE_CHECKING

from agentself.core import CapabilityCall

if TYPE_CHECKING:
    from agentself.capabilities.base import Capability


class CallRecorder:
    """Records capability calls during RECORD mode execution.

    Example:
        recorder = CallRecorder()
        proxy = CapabilityProxy(fs_capability, recorder)
        proxy.read("/some/file")  # Recorded, not executed
        print(recorder.calls)  # [CapabilityCall(...)]
    """

    def __init__(self):
        self.calls: list[CapabilityCall] = []
        self._call_stack: list[str] = []  # For detecting nested calls

    def record(
        self,
        capability_name: str,
        method_name: str,
        args: tuple,
        kwargs: dict,
    ) -> None:
        """Record a capability call."""
        self.calls.append(
            CapabilityCall(
                capability_name=capability_name,
                method_name=method_name,
                args=args,
                kwargs=kwargs,
            )
        )

    def clear(self) -> None:
        """Clear all recorded calls."""
        self.calls.clear()
        self._call_stack.clear()

    def get_calls_for(self, capability: str = None, method: str = None) -> list[CapabilityCall]:
        """Get calls matching the given filters."""
        return [c for c in self.calls if c.matches(capability, method)]

    def __len__(self) -> int:
        return len(self.calls)

    def __bool__(self) -> bool:
        """CallRecorder is always truthy (even when empty)."""
        return True


class CapabilityProxy:
    """Wraps a capability to record calls without side effects.

    In RECORD mode, method calls are intercepted and logged to the recorder.
    The actual capability method is NOT called. Instead, a simulated return
    value is produced based on type hints.

    This allows us to analyze what code will do before it does it.
    """

    def __init__(self, capability: "Capability", recorder: CallRecorder):
        """Create a proxy for a capability.

        Args:
            capability: The real capability being proxied.
            recorder: Where to record intercepted calls.
        """
        self._capability = capability
        self._recorder = recorder
        self._name = capability.name

    def __getattr__(self, name: str) -> Any:
        """Intercept attribute access.

        For callable attributes (methods), return a proxy function.
        For non-callable attributes, return the real value.
        """
        # Get the real attribute
        attr = getattr(self._capability, name)

        # Don't proxy private/dunder methods or non-callables
        if name.startswith("_") or not callable(attr):
            return attr

        # Don't proxy introspection methods - let them work normally
        if name in ("describe", "__repr__", "__str__"):
            return attr

        return self._make_proxy_method(name, attr)

    def _make_proxy_method(self, method_name: str, method: Callable) -> Callable:
        """Create a proxy function that records the call."""

        def proxy(*args, **kwargs):
            # Record the call
            self._recorder.record(self._name, method_name, args, kwargs)
            # Return a simulated value
            return self._simulate_return(method_name, method)

        # Preserve the method's signature for introspection
        proxy.__name__ = method_name
        proxy.__doc__ = method.__doc__
        try:
            proxy.__signature__ = inspect.signature(method)
        except (ValueError, TypeError):
            pass

        return proxy

    def _simulate_return(self, method_name: str, method: Callable) -> Any:
        """Generate a plausible return value based on type hints.

        This allows code to continue executing during record mode,
        even though no real work is being done.
        """
        try:
            hints = get_type_hints(method)
            return_type = hints.get("return")
        except Exception:
            return_type = None

        if return_type is None:
            return None

        # Handle common return types
        origin = getattr(return_type, "__origin__", None)

        if return_type == str:
            return f"<simulated {self._name}.{method_name} result>"
        if return_type == bool:
            return True
        if return_type == int:
            return 0
        if return_type == float:
            return 0.0
        if origin is list or return_type == list:
            return []
        if origin is dict or return_type == dict:
            return {}
        if origin is set or return_type == set:
            return set()
        if origin is tuple or return_type == tuple:
            return ()

        return None

    def __repr__(self) -> str:
        return f"<CapabilityProxy({self._capability!r})>"


class ProxyFactory:
    """Creates proxied capability dictionaries for record-mode execution."""

    def __init__(self, recorder: CallRecorder = None):
        """Create a factory.

        Args:
            recorder: Shared recorder for all proxies. If None, creates one.
        """
        self.recorder = recorder if recorder is not None else CallRecorder()

    def create_proxies(
        self, capabilities: dict[str, "Capability"]
    ) -> dict[str, CapabilityProxy]:
        """Create proxies for all capabilities in a dict."""
        return {name: CapabilityProxy(cap, self.recorder) for name, cap in capabilities.items()}

    def wrap_globals(
        self,
        base_globals: dict[str, Any],
        capabilities: dict[str, "Capability"],
    ) -> dict[str, Any]:
        """Create a globals dict with proxied capabilities.

        Returns a new dict with:
        - All items from base_globals
        - Capabilities replaced with their proxies
        - A 'caps' dict containing proxies for discovery
        """
        proxies = self.create_proxies(capabilities)

        result = base_globals.copy()
        result.update(proxies)
        result["caps"] = dict(proxies)

        return result
