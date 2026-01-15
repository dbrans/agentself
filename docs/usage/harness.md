# Harness Usage

## Defaults
- Helper commands default to `_tmp/agentself/` inside the repo.
- The library defaults to `.agentself/` inside the repo.
- Default socket: `.agentself/repl.sock`
- Default safe root: `.agentself/sandboxes/safe`

## Foreground (manual testing)
```
uv run run-harness
```

## Attach
```
uv run attach-repl
```

Attach to an active REPL using the same socket as the harness.

Prompt behavior: Enter submits when input is complete; Esc+Enter inserts a newline.

## Logging workflow (agent SOP)
```
HARNESS_LOG_FILE="./_tmp/logs/$(date +%Y%m%d-%H%M%S)-harness.log"
uv run run-harness 2>&1 | tee "$HARNESS_LOG_FILE"
```

Inspect logs with standard tools:
- `tail -f "$HARNESS_LOG_FILE"`
- `rg "error|warn" "$HARNESS_LOG_FILE"`

Stop the harness with Ctrl-C (SIGINT). If it’s in the background, `kill <pid>`.

## Troubleshooting
- `ConnectionRefusedError`: harness isn’t running or crashed; check the log file.
- Permission error writing safe root: use `_tmp/safe_root` or `--no-seed`.
