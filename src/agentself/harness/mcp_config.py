"""Load and install MCP servers from a config file."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentself.harness.runtime import HarnessRuntime

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str]
    env: dict[str, str] | None
    cwd: str | None
    disabled: bool = False
    transport: str | None = None

    @property
    def command_line(self) -> str:
        return " ".join([self.command] + self.args)


def _expand_env(value: str) -> str:
    return os.path.expandvars(value)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        logger.warning("Invalid mcp config json path=%s error=%s", path, exc)
        return {}


def _parse_servers(payload: dict[str, Any]) -> list[MCPServerConfig]:
    servers: list[MCPServerConfig] = []
    raw_servers = payload.get("mcpServers", {})
    if not isinstance(raw_servers, dict):
        return servers

    for name, cfg in raw_servers.items():
        if not isinstance(cfg, dict):
            continue
        command = cfg.get("command")
        if not command:
            continue
        args = cfg.get("args", []) or []
        env = cfg.get("env")
        cwd = cfg.get("cwd")
        transport = cfg.get("transport")
        disabled = bool(cfg.get("disabled", False))

        if isinstance(args, str):
            args = [args]
        if env is not None and not isinstance(env, dict):
            env = None

        if env:
            env = {k: _expand_env(str(v)) for k, v in env.items()}
        args = [_expand_env(str(a)) for a in args]
        command = _expand_env(str(command))
        if cwd:
            cwd = _expand_env(str(cwd))

        servers.append(
            MCPServerConfig(
                name=name,
                command=command,
                args=args,
                env=env,
                cwd=cwd,
                transport=transport,
                disabled=disabled,
            )
        )

    return servers


def load_mcp_config(path: Path) -> list[MCPServerConfig]:
    """Load MCP server configs from mcp.json."""
    payload = _load_json(path)
    return _parse_servers(payload)


async def install_from_config(runtime: HarnessRuntime, path: Path) -> list[str]:
    """Install MCP servers defined in the config file."""
    servers = load_mcp_config(path)
    if not servers:
        return []

    installed: list[str] = []
    for server in servers:
        if server.disabled:
            continue
        if server.transport and server.transport != "stdio":
            logger.warning("Skipping MCP server %s: transport=%s", server.name, server.transport)
            continue
        try:
            tools = await runtime.hub.install(
                server.name,
                server.command,
                args=server.args,
                env=server.env,
                cwd=server.cwd,
            )
            tool_specs = {
                t.name: {"description": t.description, "parameters": t.parameters}
                for t in tools
            }
            runtime.repl.inject_relay_capability(server.name, tool_specs)
            installed.append(server.name)
            logger.info("installed mcp server name=%s command=%s", server.name, server.command_line)
        except Exception as exc:
            logger.warning("failed to install mcp server name=%s error=%s", server.name, exc)

    return installed
