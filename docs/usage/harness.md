# Harness Usage

## Foreground (manual testing)
```
./scripts/run-safe-harness.sh ./_tmp/agentself.attach.sock ./_tmp/safe_root --log-file ./_tmp/agentself.log
```

## Attach
```
./scripts/attach-repl.sh ./_tmp/agentself.attach.sock
```

## Background (logs + pid)
```
./scripts/harness-start.sh
./scripts/harness-logs.sh
./scripts/harness-stop.sh
```

## Logging
- Enable with `AGENTSELF_LOG_LEVEL=DEBUG` or `--log-level debug`.
- Use `--log-file ./_tmp/agentself.log` to write to a file.

## Troubleshooting
- `ConnectionRefusedError`: harness isn’t running or crashed; check `_tmp/harness.out`.
- Permission errors writing safe root: use `_tmp/safe_root` or disable seeding.
- uv cache denied: use repo-local cache via scripts (already set in run-safe-harness).
