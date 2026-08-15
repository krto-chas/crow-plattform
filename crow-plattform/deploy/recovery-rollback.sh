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

if [[ $# -eq 0 ]]; then
  target_file="$CROW_PLATFORM_CONFIG_DIR/deployment/previous-sha"
  backup_file="$CROW_PLATFORM_CONFIG_DIR/deployment/previous-recovery-backup"
  [[ -f "$target_file" ]] || { echo "No recorded previous SHA." >&2; exit 1; }
  [[ -f "$backup_file" ]] || { echo "No recorded previous recovery backup." >&2; exit 1; }
  target_sha="$(<"$target_file")"
  target_backup="$(<"$backup_file")"
elif [[ $# -eq 2 ]]; then
  target_sha="$1"
  target_backup="$2"
else
  echo "Usage: $0 [TARGET_SHA RECOVERY.tar.gz]" >&2
  exit 2
fi

[[ -f "$target_backup" ]] || { echo "Recovery archive not found: $target_backup" >&2; exit 1; }
git -C "$CROW_PLATFORM_REPO_ROOT" cat-file -e "$target_sha^{commit}"
target_sha="$(git -C "$CROW_PLATFORM_REPO_ROOT" rev-parse "$target_sha^{commit}")"
archive_sha="$(recovery_git_sha "$target_backup")"
[[ "$archive_sha" == "$target_sha" ]] || {
  echo "Recovery archive belongs to $archive_sha, not requested target $target_sha" >&2
  exit 1
}

current_sha="$(current_git_sha)"
safety_backup="$($SCRIPT_DIR/recovery-backup.sh)"

compose stop crow-proxy crow-platform || true
git -C "$CROW_PLATFORM_REPO_ROOT" reset --hard "$target_sha"
export CROW_SOURCE_SHA="$target_sha"
restore_recovery_archive "$target_backup"
compose up -d --build

if wait_for_health && wait_for_proxy_route; then
  printf 'Recovery rollback healthy: %s -> %s\n' "$current_sha" "$target_sha"
  printf 'Safety backup of replaced state: %s\n' "$safety_backup"
  exit 0
fi

echo "Target rollback failed health gates; restoring the pre-rollback state." >&2
compose stop crow-proxy crow-platform || true
git -C "$CROW_PLATFORM_REPO_ROOT" reset --hard "$current_sha"
export CROW_SOURCE_SHA="$current_sha"
restore_recovery_archive "$safety_backup"
compose up -d --build

if wait_for_health && wait_for_proxy_route; then
  echo "Original deployment state restored after failed rollback." >&2
  exit 1
fi

echo "Emergency recovery failed; both target and original state failed health gates." >&2
exit 2
