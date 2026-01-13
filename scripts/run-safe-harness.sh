#!/usr/bin/env bash
set -euo pipefail

SOCKET_PATH=${1:-"$HOME/.agentself/repl.sock"}
SAFE_ROOT=${2:-"$HOME/.agentself/sandboxes/safe"}
EXTRA_ARGS=("${@:3}")

mkdir -p "$SAFE_ROOT"

uv run agentself \
  --profile safe \
  --safe-root "$SAFE_ROOT" \
  --attach-socket "$SOCKET_PATH" \
  "${EXTRA_ARGS[@]}"
