"""Tests for the proxy system (two-phase execution)."""

import pytest

from agentself.proxy import CallRecorder, CapabilityProxy, ProxyFactory
from agentself.capabilities.base import Capability


class MockCapability(Capability):
    """A mock capability for testing."""

    name = "mock"
    description = "A mock capability for testing."

    def read_string(self) -> str:
        """Return a string."""
        return "real string"

    def read_int(self) -> int:
        """Return an integer."""
        return 42

    def read_list(self) -> list:
        """Return a list."""
        return [1, 2, 3]

    def read_dict(self) -> dict:
        """Return a dictionary."""
        return {"key": "value"}

    def read_bool(self) -> bool:
        """Return a boolean."""
        return True

    def no_return_type(self):
        """Method with no return type hint."""
        return "something"

    def with_args(self, path: str, content: str) -> bool:
        """Method with arguments."""
        return True


class TestCallRecorder:
    """Tests for CallRecorder."""

    def test_record_call(self):
        """Test recording a call."""
        recorder = CallRecorder()

        recorder.record("fs", "read", ("/path",), {})

        assert len(recorder) == 1
        assert recorder.calls[0].capability_name == "fs"
        assert recorder.calls[0].method_name == "read"

    def test_record_multiple_calls(self):
        """Test recording multiple calls."""
        recorder = CallRecorder()

        recorder.record("fs", "read", ("/path1",), {})
        recorder.record("fs", "write", ("/path2", "content"), {})

        assert len(recorder) == 2

    def test_clear(self):
        """Test clearing recorded calls."""
        recorder = CallRecorder()
        recorder.record("fs", "read", (), {})

        recorder.clear()

        assert len(recorder) == 0

    def test_get_calls_for_capability(self):
        """Test filtering calls by capability."""
        recorder = CallRecorder()
        recorder.record("fs", "read", (), {})
        recorder.record("cmd", "run", (), {})
        recorder.record("fs", "write", (), {})

        fs_calls = recorder.get_calls_for(capability="fs")

        assert len(fs_calls) == 2
        assert all(c.capability_name == "fs" for c in fs_calls)

    def test_get_calls_for_method(self):
        """Test filtering calls by method."""
        recorder = CallRecorder()
        recorder.record("fs", "read", (), {})
        recorder.record("cmd", "run", (), {})
        recorder.record("fs", "read", (), {})

        read_calls = recorder.get_calls_for(method="read")

        assert len(read_calls) == 2
        assert all(c.method_name == "read" for c in read_calls)


class TestCapabilityProxy:
    """Tests for CapabilityProxy."""

    def test_proxy_records_call(self):
        """Test that proxy records method calls."""
        cap = MockCapability()
        recorder = CallRecorder()
        proxy = CapabilityProxy(cap, recorder)

        proxy.read_string()

        assert len(recorder) == 1
        assert recorder.calls[0].method_name == "read_string"

    def test_proxy_records_args(self):
        """Test that proxy records arguments."""
        cap = MockCapability()
        recorder = CallRecorder()
        proxy = CapabilityProxy(cap, recorder)

        proxy.with_args("/path", "content")

        assert len(recorder) == 1
        assert recorder.calls[0].args == ("/path", "content")

    def test_proxy_simulates_string_return(self):
        """Test simulated return for string type."""
        cap = MockCapability()
        recorder = CallRecorder()
        proxy = CapabilityProxy(cap, recorder)

        result = proxy.read_string()

        assert isinstance(result, str)
        assert "simulated" in result.lower()

    def test_proxy_simulates_int_return(self):
        """Test simulated return for int type."""
        cap = MockCapability()
        recorder = CallRecorder()
        proxy = CapabilityProxy(cap, recorder)

        result = proxy.read_int()

        assert result == 0

    def test_proxy_simulates_list_return(self):
        """Test simulated return for list type."""
        cap = MockCapability()
        recorder = CallRecorder()
        proxy = CapabilityProxy(cap, recorder)

        result = proxy.read_list()

        assert result == []

    def test_proxy_simulates_dict_return(self):
        """Test simulated return for dict type."""
        cap = MockCapability()
        recorder = CallRecorder()
        proxy = CapabilityProxy(cap, recorder)

        result = proxy.read_dict()

        assert result == {}

    def test_proxy_simulates_bool_return(self):
        """Test simulated return for bool type."""
        cap = MockCapability()
        recorder = CallRecorder()
        proxy = CapabilityProxy(cap, recorder)

        result = proxy.read_bool()

        assert result is True

    def test_proxy_none_for_no_type_hint(self):
        """Test that methods without type hints return None."""
        cap = MockCapability()
        recorder = CallRecorder()
        proxy = CapabilityProxy(cap, recorder)

        result = proxy.no_return_type()

        assert result is None

    def test_proxy_doesnt_call_real_method(self):
        """Test that proxy doesn't call the real method."""

        class CountingCapability(Capability):
            name = "counting"
            description = "Counts calls."
            call_count = 0

            def increment(self) -> int:
                self.call_count += 1
                return self.call_count

        cap = CountingCapability()
        recorder = CallRecorder()
        proxy = CapabilityProxy(cap, recorder)

        proxy.increment()
        proxy.increment()

        assert cap.call_count == 0  # Real method not called

    def test_proxy_allows_describe(self):
        """Test that describe() works on proxy (not intercepted)."""
        cap = MockCapability()
        recorder = CallRecorder()
        proxy = CapabilityProxy(cap, recorder)

        result = proxy.describe()

        # describe() should work normally and not be recorded
        assert "mock" in result.lower()
        # describe() should not be recorded as a capability call
        assert len(recorder.get_calls_for(method="describe")) == 0

    def test_proxy_passes_through_attributes(self):
        """Test that non-callable attributes pass through."""
        cap = MockCapability()
        recorder = CallRecorder()
        proxy = CapabilityProxy(cap, recorder)

        assert proxy.name == "mock"
        assert proxy.description == "A mock capability for testing."


class TestProxyFactory:
    """Tests for ProxyFactory."""

    def test_create_proxies(self):
        """Test creating proxies for multiple capabilities."""
        cap1 = MockCapability()
        cap2 = MockCapability()
        factory = ProxyFactory()

        proxies = factory.create_proxies({"cap1": cap1, "cap2": cap2})

        assert "cap1" in proxies
        assert "cap2" in proxies
        assert isinstance(proxies["cap1"], CapabilityProxy)
        assert isinstance(proxies["cap2"], CapabilityProxy)

    def test_shared_recorder(self):
        """Test that proxies share a recorder."""
        cap1 = MockCapability()
        cap2 = MockCapability()
        factory = ProxyFactory()

        proxies = factory.create_proxies({"cap1": cap1, "cap2": cap2})

        proxies["cap1"].read_string()
        proxies["cap2"].read_int()

        assert len(factory.recorder) == 2

    def test_wrap_globals(self):
        """Test wrapping a globals dict."""
        cap = MockCapability()
        factory = ProxyFactory()
        base = {"__builtins__": {}, "x": 42}

        wrapped = factory.wrap_globals(base, {"mock": cap})

        assert wrapped["x"] == 42
        assert "mock" in wrapped
        assert isinstance(wrapped["mock"], CapabilityProxy)
        assert "caps" in wrapped
        assert "mock" in wrapped["caps"]
