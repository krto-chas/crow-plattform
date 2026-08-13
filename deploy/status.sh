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
echo "https_site=$CROW_PROXY_SITE"
compose ps crow-platform crow-proxy

if wait_for_health 1; then
  echo "backend_health=ok"
else
  echo "backend_health=failed"
  exit 1
fi

if wait_for_proxy_route 1; then
  echo "https_route=ok"
else
  echo "https_route=failed"
  exit 1
fi

du -sh "$CROW_PLATFORM_DATA_DIR" "$CROW_PLATFORM_CONFIG_DIR" 2>/dev/null || true
