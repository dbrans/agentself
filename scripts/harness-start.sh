#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SOCKET_PATH=${1:-"$HOME/.agentself/repl.sock"}
SAFE_ROOT=${2:-"$HOME/.agentself/sandboxes/safe"}
LOG_FILE=${3:-""}
PID_FILE=${4:-"$REPO_ROOT/_tmp/agentself.pid"}
OUT_FILE=${HARNESS_STDOUT:-"$REPO_ROOT/_tmp/harness.out"}

if [ "$#" -ge 4 ]; then
  shift 4
elif [ "$#" -eq 3 ]; then
  shift 3
elif [ "$#" -eq 2 ]; then
  shift 2
elif [ "$#" -eq 1 ]; then
  shift 1
fi

if [ -z "$LOG_FILE" ]; then
  TS="$(date +"%Y%m%d-%H%M%S")"
  LOG_FILE="$REPO_ROOT/_tmp/agentself-$TS.log"
fi

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$PID_FILE")" "$(dirname "$OUT_FILE")"

if [ -f "$PID_FILE" ]; then
  if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Harness already running (pid $(cat "$PID_FILE"))."
    exit 0
  fi
  rm -f "$PID_FILE"
fi

AGENTSELF_LOG_LEVEL=${AGENTSELF_LOG_LEVEL:-INFO} \
  nohup "$SCRIPT_DIR/run-safe-harness.sh" \
    "$SOCKET_PATH" \
    "$SAFE_ROOT" \
    --log-file "$LOG_FILE" \
    "$@" \
    > "$OUT_FILE" 2>&1 &

echo $! > "$PID_FILE"
echo "Started harness pid=$(cat "$PID_FILE") socket=$SOCKET_PATH log=$LOG_FILE"
