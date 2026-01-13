#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LOG_FILE=${1:-"$REPO_ROOT/_tmp/agentself.log"}

if [ ! -f "$LOG_FILE" ]; then
  echo "No log file at $LOG_FILE"
  exit 1
fi

tail -n 200 -f "$LOG_FILE"
