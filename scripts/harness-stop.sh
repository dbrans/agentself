#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PID_FILE=${1:-"$REPO_ROOT/_tmp/agentself.pid"}

if [ ! -f "$PID_FILE" ]; then
  echo "No pid file at $PID_FILE"
  exit 1
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "Stopped harness pid=$PID"
else
  echo "Process $PID not running"
fi

rm -f "$PID_FILE"
