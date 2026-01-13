#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SOCKET_PATH=${1:-"$HOME/.agentself/repl.sock"}
SAFE_ROOT=${2:-"$HOME/.agentself/sandboxes/safe"}
CACHE_ROOT=${XDG_CACHE_HOME:-"$REPO_ROOT/_tmp/uv-cache"}
if [ "$#" -ge 2 ]; then
  shift 2
elif [ "$#" -eq 1 ]; then
  shift 1
fi

mkdir -p "$SAFE_ROOT" "$CACHE_ROOT"

XDG_CACHE_HOME="$CACHE_ROOT" UV_CACHE_DIR="$CACHE_ROOT/uv" uv run agentself \
  --profile safe \
  --safe-root "$SAFE_ROOT" \
  --attach-socket "$SOCKET_PATH" \
  "$@"
