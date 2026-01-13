# Safe Harness Runbook

## Start (foreground)
```
./scripts/run-safe-harness.sh ./_tmp/agentself.attach.sock ./_tmp/safe_root --log-file ./_tmp/agentself.log
```

## Start (background)
```
./scripts/harness-start.sh
./scripts/harness-logs.sh
```

## Attach
```
./scripts/attach-repl.sh ./_tmp/agentself.attach.sock
```

## Stop
```
./scripts/harness-stop.sh
```

## Troubleshooting
- `ConnectionRefusedError`: harness not running; check `_tmp/harness.out`.
- Permission error writing safe root: use `_tmp/safe_root` or `--no-seed`.
- Socket exists but no listener: stale socket; restart harness.
