"""Attach server for connecting to a running REPL process."""

from __future__ import annotations

import json
import logging
import socketserver
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from agentself.harness.logging_utils import abbreviate
from agentself.harness.runtime import HarnessRuntime

logger = logging.getLogger(__name__)


class AttachRequestHandler(socketserver.StreamRequestHandler):
    """Handle attach client requests."""

    def handle(self) -> None:
        for line in self.rfile:
            if not line:
                break
            try:
                request = json.loads(line.decode("utf-8").strip())
            except json.JSONDecodeError as exc:
                logger.warning("invalid json error=%s", exc)
                response = {"success": False, "error": f"Invalid JSON: {exc}"}
                self._send_response(response)
                continue

            op = request.get("op")
            wait = request.get("wait", False)
            detail = ""
            if op == "execute":
                detail = f" code={abbreviate(request.get('code', ''))}"
            elif op == "describe_capability":
                detail = f" name={request.get('name', '')}"

            logger.debug("request op=%s wait=%s%s", op, wait, detail)
            start = time.perf_counter()
            try:
                response = self.server.dispatch(request)  # type: ignore[attr-defined]
            except Exception:
                logger.exception("dispatch failed op=%s", op)
                response = {"success": False, "error": "Dispatch failed"}
            duration_ms = int((time.perf_counter() - start) * 1000)
            if response.get("success", True):
                logger.debug("response op=%s success=True duration_ms=%s", op, duration_ms)
            else:
                logger.debug(
                    "response op=%s success=False duration_ms=%s error=%s",
                    op,
                    duration_ms,
                    abbreviate(str(response.get("error", ""))),
                )
            self._send_response(response)

    def _send_response(self, response: dict[str, Any]) -> None:
        payload = json.dumps(response).encode("utf-8") + b"\n"
        self.wfile.write(payload)
        self.wfile.flush()


class AttachServerBase:
    """Shared dispatch logic for attach servers."""

    def __init__(self, runtime: HarnessRuntime):
        self.runtime = runtime

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        op = request.get("op")
        wait = bool(request.get("wait", False))
        timeout = request.get("timeout")

        if op == "ping":
            return {"success": True, "busy": self.runtime.busy()}

        if op in {
            "execute",
            "state",
            "list_capabilities",
            "describe_capability",
            "export_state",
            "import_state",
        }:
            if not self.runtime.acquire(wait=wait, timeout=timeout):
                logger.debug("reject op=%s reason=busy wait=%s timeout=%s", op, wait, timeout)
                return {"success": False, "error": "REPL busy"}
            try:
                return self._dispatch_locked(op, request)
            finally:
                self.runtime.release()

        return {"success": False, "error": f"Unknown op: {op}"}

    def _dispatch_locked(self, op: str, request: dict[str, Any]) -> dict[str, Any]:
        if op == "execute":
            code = request.get("code", "")
            result = self.runtime.repl.execute(code)
            return asdict(result)
        if op == "state":
            result = self.runtime.repl.state()
            return asdict(result)
        if op == "list_capabilities":
            return {"success": True, "capabilities": self.runtime.repl.list_capabilities()}
        if op == "describe_capability":
            name = request.get("name", "")
            result = self.runtime.repl.execute(f"{name}.describe()")
            if result.success:
                return {"success": True, "description": result.return_value}
            return {"success": False, "error": f"Capability '{name}' not found or has no describe()"}
        if op == "export_state":
            return {"success": True, "state": self.runtime.repl.export_state()}
        if op == "import_state":
            state = request.get("state", {})
            return {"success": True, "result": self.runtime.repl.import_state(state)}
        return {"success": False, "error": f"Unhandled op: {op}"}


class AttachServer(AttachServerBase, socketserver.ThreadingUnixStreamServer):
    """Unix socket server that proxies requests to the shared REPL."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, socket_path: Path, runtime: HarnessRuntime):
        self.socket_path = socket_path
        if self.socket_path.exists():
            self.socket_path.unlink()
        AttachServerBase.__init__(self, runtime)
        socketserver.ThreadingUnixStreamServer.__init__(
            self,
            str(self.socket_path),
            AttachRequestHandler,
        )

    def server_close(self) -> None:
        super().server_close()
        if self.socket_path.exists():
            self.socket_path.unlink()


class AttachTCPServer(AttachServerBase, socketserver.ThreadingTCPServer):
    """TCP server that proxies requests to the shared REPL."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, host: str, port: int, runtime: HarnessRuntime):
        AttachServerBase.__init__(self, runtime)
        socketserver.ThreadingTCPServer.__init__(
            self,
            (host, port),
            AttachRequestHandler,
        )
