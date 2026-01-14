# Harness Usage

## Foreground (manual testing)
```
./scripts/run-harness.sh ./_tmp/agentself.attach.sock ./_tmp/safe_root
```

## Attach
```
./scripts/attach-repl.sh ./_tmp/agentself.attach.sock
```

## Logging workflow (agent SOP)
```
LOG_FILE="./_tmp/harness-$(date +%Y%m%d-%H%M%S).log"
./scripts/run-harness.sh ./_tmp/agentself.attach.sock ./_tmp/safe_root 2>&1 | tee "$LOG_FILE"
```

Inspect logs with standard tools:
- `tail -f "$LOG_FILE"`
- `rg "error|warn" "$LOG_FILE"`

Stop the harness with Ctrl-C (SIGINT). If it’s in the background, `kill <pid>`.

## Troubleshooting
- `ConnectionRefusedError`: harness isn’t running or crashed; check the log file.
- Permission error writing safe root: use `_tmp/safe_root` or `--no-seed`.
