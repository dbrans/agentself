#!/usr/bin/env bash
set -euo pipefail

SOCKET_PATH=${1:-"$HOME/.agentself/repl.sock"}
EXTRA_ARGS=("${@:2}")

uv run agentself-attach --socket "$SOCKET_PATH" "${EXTRA_ARGS[@]}"
