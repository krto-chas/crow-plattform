#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/crow-platform-ops.sh
source "$SCRIPT_DIR/lib/crow-platform-ops.sh"
# shellcheck source=deploy/lib/crow-platform-recovery.sh
source "$SCRIPT_DIR/lib/crow-platform-recovery.sh"

load_platform_env
require_command docker
require_command git
require_command curl
require_command tar
require_command sha256sum
require_clean_git

previous_sha="$(current_git_sha)"
backup_path="$($SCRIPT_DIR/recovery-backup.sh)"
mkdir -p "$CROW_PLATFORM_CONFIG_DIR/deployment"
printf '%s\n' "$previous_sha" >"$CROW_PLATFORM_CONFIG_DIR/deployment/previous-sha"
printf '%s\n' "$backup_path" >"$CROW_PLATFORM_CONFIG_DIR/deployment/previous-recovery-backup"

git -C "$CROW_PLATFORM_REPO_ROOT" pull --ff-only
new_sha="$(current_git_sha)"
export CROW_SOURCE_SHA="$new_sha"

if compose up -d --build && wait_for_health && wait_for_proxy_route; then
  printf 'Recovery-gated upgrade healthy: %s -> %s\n' "$previous_sha" "$new_sha"
  exit 0
fi

echo "Upgrade stack gate failed; restoring code and state for $previous_sha" >&2
compose stop crow-proxy crow-platform || true
git -C "$CROW_PLATFORM_REPO_ROOT" reset --hard "$previous_sha"
export CROW_SOURCE_SHA="$previous_sha"
restore_recovery_archive "$backup_path"
compose up -d --build

if wait_for_health && wait_for_proxy_route; then
  echo "Full rollback succeeded. Restored recovery archive: $backup_path" >&2
  exit 1
fi

echo "Full rollback could not re-establish the backend + HTTPS health gate." >&2
exit 2
