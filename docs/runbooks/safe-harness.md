# Safe Harness Runbook

## Defaults
- Helper scripts default to `_tmp/agentself/` inside the repo.
- The library defaults to `.agentself/` (override with `AGENTSELF_HOME`).
- Default socket: `$AGENTSELF_HOME/repl.sock`
- Default safe root: `$AGENTSELF_HOME/sandboxes/safe`

## Start (foreground)
```
./scripts/run-harness.sh
```

## Attach
```
./scripts/attach-repl.sh
```

Attach to an active REPL using the same socket as the harness. If you run multiple harnesses,
pass a unique socket path (or set `AGENTSELF_ATTACH_SOCKET` for that terminal).

Prompt behavior: Enter submits when input is complete; Esc+Enter inserts a newline.

## Logging
```
LOG_FILE="./_tmp/harness-$(date +%Y%m%d-%H%M%S).log"
./scripts/run-harness.sh 2>&1 | tee "$LOG_FILE"
```

## Stop
- Ctrl-C in the terminal running the harness.
- Or `kill <pid>` if running in the background.

## Troubleshooting
- `ConnectionRefusedError`: harness not running; check the log file.
- Socket exists but no listener: restart the harness.
- Permission error writing safe root: use `_tmp/safe_root` or `--no-seed`.
