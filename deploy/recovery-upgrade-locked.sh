#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export COMPOSE_FILE="$REPO_ROOT/compose.yaml:$REPO_ROOT/compose.locked.yaml"
exec bash "$SCRIPT_DIR/recovery-upgrade.sh" "$@"
