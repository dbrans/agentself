#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

AGENTSELF_HOME="${AGENTSELF_HOME:-"$REPO_ROOT/_tmp/agentself"}"
export AGENTSELF_HOME
SOCKET_PATH=${1:-"$AGENTSELF_HOME/repl.sock"}
SAFE_ROOT=${2:-"$AGENTSELF_HOME/sandboxes/safe"}
if [ "$#" -ge 2 ]; then
  shift 2
elif [ "$#" -eq 1 ]; then
  shift 1
fi

mkdir -p "$SAFE_ROOT"

uv run agentself \
  --profile safe \
  --safe-root "$SAFE_ROOT" \
  --attach-socket "$SOCKET_PATH" \
  "$@"
