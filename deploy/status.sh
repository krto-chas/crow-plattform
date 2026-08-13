#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/crow-platform-ops.sh
source "$SCRIPT_DIR/lib/crow-platform-ops.sh"

load_platform_env
require_command docker
require_command git
require_command curl

echo "git_sha=$(current_git_sha)"
echo "data_dir=$CROW_PLATFORM_DATA_DIR"
echo "config_dir=$CROW_PLATFORM_CONFIG_DIR"
echo "backup_dir=$CROW_PLATFORM_BACKUP_DIR"
compose ps crow-platform

if wait_for_health 1; then
  echo "health=ok"
else
  echo "health=failed"
  exit 1
fi

du -sh "$CROW_PLATFORM_DATA_DIR" "$CROW_PLATFORM_CONFIG_DIR" 2>/dev/null || true
