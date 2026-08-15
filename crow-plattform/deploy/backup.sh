#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/crow-platform-ops.sh
source "$SCRIPT_DIR/lib/crow-platform-ops.sh"

load_platform_env
require_command docker
require_command tar
require_command sha256sum
require_command git

mkdir -p "$CROW_PLATFORM_BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$CROW_PLATFORM_BACKUP_DIR/crow-platform-$timestamp.tar.gz"
source_sha="$(current_git_sha)"
was_running=false

if service_is_running; then
  was_running=true
  compose stop crow-platform
fi

restart_if_needed() {
  if [[ "$was_running" == true ]]; then
    compose up -d crow-platform
    wait_for_health
  fi
}
trap restart_if_needed EXIT

create_backup_archive "$archive" "$source_sha"
printf '%s\n' "$archive"
