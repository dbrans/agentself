# Safe Harness Runbook

## Start (foreground)
```
./scripts/run-harness.sh ./_tmp/agentself.attach.sock ./_tmp/safe_root
```

## Attach
```
./scripts/attach-repl.sh ./_tmp/agentself.attach.sock
```

## Logging
```
LOG_FILE="./_tmp/harness-$(date +%Y%m%d-%H%M%S).log"
./scripts/run-harness.sh ./_tmp/agentself.attach.sock ./_tmp/safe_root 2>&1 | tee "$LOG_FILE"
```

## Stop
- Ctrl-C in the terminal running the harness.
- Or `kill <pid>` if running in the background.

## Troubleshooting
- `ConnectionRefusedError`: harness not running; check the log file.
- Socket exists but no listener: restart the harness.
- Permission error writing safe root: use `_tmp/safe_root` or `--no-seed`.
