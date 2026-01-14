#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SOCKET_PATH=${1:-"$HOME/.agentself/repl.sock"}

if [ "$#" -ge 1 ]; then
  shift 1
fi

uv run agentself-attach --socket "$SOCKET_PATH" "$@"
