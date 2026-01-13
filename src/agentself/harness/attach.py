"""CLI for attaching to a running REPL server."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any, TextIO


def _default_socket() -> Path:
    return Path(os.environ.get("AGENTSELF_ATTACH_SOCKET", "~/.agentself/repl.sock")).expanduser()


def _send_request(sock_file: TextIO, request: dict[str, Any]) -> dict[str, Any]:
    sock_file.write(json.dumps(request) + "\n")
    sock_file.flush()
    response_line = sock_file.readline()
    if not response_line:
        raise RuntimeError("Attach server closed connection")
    return json.loads(response_line)


def _print_result(result: dict[str, Any]) -> None:
    if "error" in result and not result.get("success", True):
        print(f"[error] {result['error']}")
        return
    if "return_value" in result:
        if result.get("stdout"):
            print(result["stdout"], end="")
        if result.get("stderr"):
            print(result["stderr"], end="", file=sys.stderr)
        if result.get("return_value") is not None:
            print(result["return_value"])
        return
    print(json.dumps(result, indent=2))


def _interactive(sock_file: TextIO, wait: bool) -> None:
    print("Attached. Commands: :state, :caps, :desc <name>, :block, :quit")
    while True:
        try:
            line = input("repl> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line.strip():
            continue

        if line.strip() in {":q", ":quit", ":exit"}:
            break
        if line.strip() == ":state":
            result = _send_request(sock_file, {"op": "state", "wait": wait})
            _print_result(result)
            continue
        if line.strip() == ":caps":
            result = _send_request(sock_file, {"op": "list_capabilities", "wait": wait})
            _print_result(result)
            continue
        if line.startswith(":desc "):
            name = line.split(" ", 1)[1].strip()
            result = _send_request(
                sock_file,
                {"op": "describe_capability", "name": name, "wait": wait},
            )
            _print_result(result)
            continue
        if line.strip() == ":block":
            print("Enter code, finish with :end")
            lines = []
            while True:
                block_line = input("... ")
                if block_line.strip() == ":end":
                    break
                lines.append(block_line)
            code = "\n".join(lines)
            result = _send_request(sock_file, {"op": "execute", "code": code, "wait": wait})
            _print_result(result)
            continue

        result = _send_request(sock_file, {"op": "execute", "code": line, "wait": wait})
        _print_result(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach to a running agentself REPL server.")
    parser.add_argument("--socket", default=str(_default_socket()), help="Unix socket path")
    parser.add_argument("--wait", action="store_true", help="Wait for REPL if busy")
    parser.add_argument("--exec", dest="exec_code", help="Execute code and exit")
    args = parser.parse_args()

    socket_path = Path(args.socket).expanduser()

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(socket_path))
        sock_file = sock.makefile("rw", encoding="utf-8")

        if args.exec_code:
            code = args.exec_code
            if code == "-":
                code = sys.stdin.read()
            result = _send_request(sock_file, {"op": "execute", "code": code, "wait": args.wait})
            _print_result(result)
            return

        _interactive(sock_file, args.wait)


if __name__ == "__main__":
    main()
