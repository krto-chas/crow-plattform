#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/crow-platform-ops.sh
source "$SCRIPT_DIR/lib/crow-platform-ops.sh"

load_platform_env
require_command docker
require_command git
require_command curl
require_clean_git

previous_sha="$(current_git_sha)"
backup_path="$($SCRIPT_DIR/backup.sh)"
mkdir -p "$CROW_PLATFORM_CONFIG_DIR/deployment"
printf '%s\n' "$previous_sha" >"$CROW_PLATFORM_CONFIG_DIR/deployment/previous-sha"
printf '%s\n' "$backup_path" >"$CROW_PLATFORM_CONFIG_DIR/deployment/previous-backup"

git -C "$CROW_PLATFORM_REPO_ROOT" pull --ff-only
new_sha="$(current_git_sha)"

if compose up -d --build && wait_for_health; then
  printf 'Upgrade healthy: %s -> %s\n' "$previous_sha" "$new_sha"
  exit 0
fi

echo "Upgrade health gate failed; rolling code back to $previous_sha" >&2
git -C "$CROW_PLATFORM_REPO_ROOT" reset --hard "$previous_sha"
compose up -d --build
wait_for_health

echo "Code rollback succeeded. Pre-upgrade backup: $backup_path" >&2
exit 1
