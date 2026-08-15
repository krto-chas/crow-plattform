#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/crow-platform-ops.sh
source "$SCRIPT_DIR/lib/crow-platform-ops.sh"
# shellcheck source=deploy/lib/crow-platform-recovery.sh
source "$SCRIPT_DIR/lib/crow-platform-recovery.sh"

load_platform_env
require_command docker
require_command tar
require_command sha256sum
require_command git
require_command curl

mkdir -p "$CROW_PLATFORM_BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$CROW_PLATFORM_BACKUP_DIR/crow-platform-recovery-$timestamp.tar.gz"
source_sha="$(current_git_sha)"
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

restart_previous_stack() {
  if [[ "$proxy_was_running" == true ]]; then
    compose up -d crow-platform crow-proxy
    wait_for_health
    wait_for_proxy_route
  elif [[ "$platform_was_running" == true ]]; then
    compose up -d crow-platform
    wait_for_health
  fi
}

trap restart_previous_stack EXIT
create_recovery_archive "$archive" "$source_sha"
restart_previous_stack
trap - EXIT
printf '%s\n' "$archive"
