#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LOG_FILE=${1:-""}

if [ -z "$LOG_FILE" ]; then
  LOG_FILE="$(ls -t "$REPO_ROOT"/_tmp/agentself-*.log 2>/dev/null | head -n 1 || true)"
fi

if [ -z "$LOG_FILE" ] || [ ! -f "$LOG_FILE" ]; then
  echo "No log file found under $REPO_ROOT/_tmp"
  exit 1
fi

tail -n 200 -f "$LOG_FILE"
