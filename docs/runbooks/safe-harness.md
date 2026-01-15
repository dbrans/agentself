# Safe Harness Runbook

## Defaults
- Helper commands default to `_tmp/agentself/` inside the repo.
- The library defaults to `.agentself/` inside the repo.
- Default socket: `.agentself/repl.sock`
- Default safe root: `.agentself/sandboxes/safe`

## Start (foreground)
```
uv run run-harness
```

## Attach
```
uv run attach-repl
```

Attach to an active REPL using the same socket as the harness.

Prompt behavior: Enter submits when input is complete; Esc+Enter inserts a newline.

## Logging
```
LOG_FILE="./_tmp/logs/$(date +%Y%m%d-%H%M%S)-harness.log"
uv run run-harness 2>&1 | tee "$LOG_FILE"
```

## Stop
- Ctrl-C in the terminal running the harness.
- Or `kill <pid>` if running in the background.

## Troubleshooting
- `ConnectionRefusedError`: harness not running; check the log file.
- Socket exists but no listener: restart the harness.
- Permission error writing safe root: use `_tmp/safe_root` or `--no-seed`.
