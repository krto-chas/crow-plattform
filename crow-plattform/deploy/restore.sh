#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/crow-platform-ops.sh
source "$SCRIPT_DIR/lib/crow-platform-ops.sh"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 BACKUP.tar.gz" >&2
  exit 2
fi
archive="$1"
[[ -f "$archive" ]] || { echo "Backup not found: $archive" >&2; exit 1; }

load_platform_env
require_command docker
require_command tar
require_command sha256sum

was_running=false
if service_is_running; then
  was_running=true
  compose stop crow-platform
fi

restore_backup_archive "$archive"

if [[ "$was_running" == true ]]; then
  compose up -d crow-platform
  wait_for_health
fi

echo "Restore completed from $archive"
