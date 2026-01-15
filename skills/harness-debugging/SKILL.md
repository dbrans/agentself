---
name: harness-debugging
description: SOP for running the harness with logs and inspecting output.
---
# Harness debugging SOP

Goal: run the harness like a normal dev server, capture logs via shell redirection, and inspect with standard tools.

## Start + log capture
```
LOG_FILE="./_tmp/harness-$(date +%Y%m%d-%H%M%S).log"
uv run run-harness 2>&1 | tee "$LOG_FILE"
```

## Inspect logs
- `tail -f "$LOG_FILE"`
- `rg "error|warn" "$LOG_FILE"`
- `head -n 50 "$LOG_FILE"`

## Stop
- Ctrl-C in the terminal running the harness.
- If backgrounded: `kill <pid>`.
