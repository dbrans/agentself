# Harness Usage

## Defaults
- Helper scripts default to `_tmp/agentself/` inside the repo.
- The library defaults to `.agentself/` (override with `AGENTSELF_HOME`).
- Default socket: `$AGENTSELF_HOME/repl.sock`
- Default safe root: `$AGENTSELF_HOME/sandboxes/safe`

## Foreground (manual testing)
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

## Logging workflow (agent SOP)
```
HARNESS_LOG_FILE="./_tmp/logs/$(date +%Y%m%d-%H%M%S)-harness.log"
./scripts/run-harness.sh 2>&1 | tee "$HARNESS_LOG_FILE"
```

Inspect logs with standard tools:
- `tail -f "$HARNESS_LOG_FILE"`
- `rg "error|warn" "$HARNESS_LOG_FILE"`

Stop the harness with Ctrl-C (SIGINT). If it’s in the background, `kill <pid>`.

## Troubleshooting
- `ConnectionRefusedError`: harness isn’t running or crashed; check the log file.
- Permission error writing safe root: use `_tmp/safe_root` or `--no-seed`.
