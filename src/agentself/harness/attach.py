"""CLI for attaching to a running REPL server."""

from __future__ import annotations

import argparse
import atexit
import codeop
import json
import socket
import sys
from pathlib import Path
from typing import Any, TextIO

from agentself.paths import ATTACH_HISTORY_PATH, ATTACH_SOCKET_PATH
try:
    import readline
except ImportError:  # pragma: no cover - platform dependent
    readline = None

try:  # pragma: no cover - optional dependency
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings
except Exception:  # pragma: no cover - optional dependency
    PromptSession = None
    FileHistory = None
    KeyBindings = None


def _default_socket() -> Path:
    return ATTACH_SOCKET_PATH


def _history_path() -> Path:
    return ATTACH_HISTORY_PATH


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


def _handle_line(sock_file: TextIO, wait: bool, line: str) -> bool:
    stripped = line.strip()

    if not stripped:
        return True

    if stripped in {":q", ":quit", ":exit"}:
        return False
    if stripped == ":state":
        result = _send_request(sock_file, {"op": "state", "wait": wait})
        _print_result(result)
        return True
    if stripped == ":caps":
        result = _send_request(sock_file, {"op": "list_capabilities", "wait": wait})
        _print_result(result)
        return True
    if stripped.startswith(":desc "):
        name = stripped.split(" ", 1)[1].strip()
        result = _send_request(
            sock_file,
            {"op": "describe_capability", "name": name, "wait": wait},
        )
        _print_result(result)
        return True
    if stripped == ":block":
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
        return True

    result = _send_request(sock_file, {"op": "execute", "code": line, "wait": wait})
    _print_result(result)
    return True


def _configure_readline(history_path: Path) -> None:
    if readline is None:
        return

    readline.parse_and_bind("set editing-mode emacs")
    readline.parse_and_bind('"\\e[1;3C": forward-word')
    readline.parse_and_bind('"\\e[1;3D": backward-word')
    readline.parse_and_bind('"\\e[1;9C": forward-word')
    readline.parse_and_bind('"\\e[1;9D": backward-word')
    readline.parse_and_bind('"\\e\\e[C": forward-word')
    readline.parse_and_bind('"\\e\\e[D": backward-word')

    history_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        readline.read_history_file(str(history_path))
    except FileNotFoundError:
        pass

    def _save_history() -> None:
        try:
            readline.write_history_file(str(history_path))
        except OSError:
            pass

    atexit.register(_save_history)


def _interactive_readline(sock_file: TextIO, wait: bool) -> None:
    _configure_readline(_history_path())
    print("Attached. Commands: :state, :caps, :desc <name>, :block, :quit")
    while True:
        try:
            line = input("repl> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not _handle_line(sock_file, wait, line):
            break


def _interactive_prompt_toolkit(sock_file: TextIO, wait: bool) -> None:
    history_path = _history_path()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    key_bindings = KeyBindings()

    def _input_complete(text: str) -> bool:
        try:
            return codeop.compile_command(text, symbol="exec") is not None
        except (SyntaxError, ValueError, OverflowError):
            return True

    @key_bindings.add("enter")
    def _(event) -> None:
        buffer = event.current_buffer
        if buffer.cursor_position != len(buffer.text):
            buffer.insert_text("\n")
        elif _input_complete(buffer.text):
            buffer.validate_and_handle()
        else:
            buffer.insert_text("\n")

    @key_bindings.add("escape", "enter")
    def _(event) -> None:
        event.current_buffer.insert_text("\n")

    @key_bindings.add("escape", "left")
    def _(event) -> None:
        event.current_buffer.cursor_backward_word(count=1)

    @key_bindings.add("escape", "right")
    def _(event) -> None:
        event.current_buffer.cursor_forward_word(count=1)

    session = PromptSession(
        "repl> ",
        multiline=True,
        key_bindings=key_bindings,
        history=FileHistory(str(history_path)),
    )

    print("Attached. Commands: :state, :caps, :desc <name>, :block, :quit")
    print("Tip: Enter submits when complete; Esc+Enter inserts a newline.")
    while True:
        try:
            line = session.prompt()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not _handle_line(sock_file, wait, line):
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach to a running agentself REPL server.")
    parser.add_argument("--socket", default=str(_default_socket()), help="Unix socket path")
    parser.add_argument("--wait", action="store_true", help="Wait for REPL if busy")
    parser.add_argument("--exec", dest="exec_code", help="Execute code and exit")
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Disable prompt_toolkit even if installed.",
    )
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

        if PromptSession is not None and not args.plain:
            _interactive_prompt_toolkit(sock_file, args.wait)
        else:
            _interactive_readline(sock_file, args.wait)


if __name__ == "__main__":
    main()
