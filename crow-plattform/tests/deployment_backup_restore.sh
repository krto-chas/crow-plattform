#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=deploy/lib/crow-platform-ops.sh
source "$REPO_ROOT/deploy/lib/crow-platform-ops.sh"

workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT
export CROW_PLATFORM_DATA_DIR="$workspace/data"
export CROW_PLATFORM_CONFIG_DIR="$workspace/config"
export CROW_PLATFORM_BACKUP_DIR="$workspace/backups"
mkdir -p "$CROW_PLATFORM_DATA_DIR/project-a" "$CROW_PLATFORM_CONFIG_DIR/audit"
printf 'original-data\n' >"$CROW_PLATFORM_DATA_DIR/project-a/state.txt"
printf 'original-config\n' >"$CROW_PLATFORM_CONFIG_DIR/audit/events.jsonl"

archive="$CROW_PLATFORM_BACKUP_DIR/test.tar.gz"
create_backup_archive "$archive" "test-sha"

printf 'mutated-data\n' >"$CROW_PLATFORM_DATA_DIR/project-a/state.txt"
printf 'mutated-config\n' >"$CROW_PLATFORM_CONFIG_DIR/audit/events.jsonl"
printf 'extra\n' >"$CROW_PLATFORM_DATA_DIR/extra.txt"

restore_backup_archive "$archive"

test "$(<"$CROW_PLATFORM_DATA_DIR/project-a/state.txt")" = "original-data"
test "$(<"$CROW_PLATFORM_CONFIG_DIR/audit/events.jsonl")" = "original-config"
test ! -e "$CROW_PLATFORM_DATA_DIR/extra.txt"

echo "backup/restore round-trip passed"
bash "$REPO_ROOT/tests/deployment_bootstrap.sh"
bash "$REPO_ROOT/tests/deployment_recovery.sh"
bash "$REPO_ROOT/tests/deployment_locked_build.sh"
