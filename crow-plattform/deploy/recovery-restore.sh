#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/crow-platform-ops.sh
source "$SCRIPT_DIR/lib/crow-platform-ops.sh"
# shellcheck source=deploy/lib/crow-platform-recovery.sh
source "$SCRIPT_DIR/lib/crow-platform-recovery.sh"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 RECOVERY.tar.gz" >&2
  exit 2
fi
archive="$1"
[[ -f "$archive" ]] || { echo "Recovery archive not found: $archive" >&2; exit 1; }

load_platform_env
require_command docker
require_command tar
require_command sha256sum
require_command curl

platform_was_running=false
proxy_was_running=false
if proxy_is_running; then
  proxy_was_running=true
  compose stop crow-proxy
fi
if service_is_running; then
  platform_was_running=true
  compose stop crow-platform
fi

restore_recovery_archive "$archive"

if [[ "$proxy_was_running" == true ]]; then
  compose up -d crow-platform crow-proxy
  wait_for_health
  wait_for_proxy_route
elif [[ "$platform_was_running" == true ]]; then
  compose up -d crow-platform
  wait_for_health
fi

echo "Recovery restore completed from $archive"
