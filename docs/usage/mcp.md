# MCP Usage

## Auto-install from mcp.json
By default the harness loads `mcp.json` if present.

Disable with:
```
uv run agentself --no-mcp-config
```

## mcp.json format (Claude Code style)
```
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp", "--api-key", "${CONTEXT7_API_KEY}"],
      "env": {"CONTEXT7_API_KEY": "${CONTEXT7_API_KEY}"},
      "disabled": true
    }
  }
}
```

Notes:
- Environment variables in `command`, `args`, `env`, and `cwd` are expanded.
- Only `stdio` transport is currently supported.
