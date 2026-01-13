"""Tests for MCP config loading."""

import json
import os
from pathlib import Path

from agentself.harness.mcp_config import load_mcp_config


def test_load_mcp_config_expands_env(tmp_path: Path) -> None:
    os.environ["MCP_TEST_VALUE"] = "ok"
    config = {
        "mcpServers": {
            "alpha": {
                "command": "echo",
                "args": ["${MCP_TEST_VALUE}"],
                "env": {"TOKEN": "${MCP_TEST_VALUE}"},
                "cwd": "${MCP_TEST_VALUE}",
            },
            "beta": {
                "command": "noop",
                "disabled": True,
            },
        }
    }
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    servers = load_mcp_config(path)
    alpha = next(s for s in servers if s.name == "alpha")

    assert alpha.command == "echo"
    assert alpha.args == ["ok"]
    assert alpha.env == {"TOKEN": "ok"}
    assert alpha.cwd == "ok"
