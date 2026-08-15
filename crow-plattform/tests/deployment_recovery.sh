#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=deploy/lib/crow-platform-ops.sh
source "$REPO_ROOT/deploy/lib/crow-platform-ops.sh"
# shellcheck source=deploy/lib/crow-platform-recovery.sh
source "$REPO_ROOT/deploy/lib/crow-platform-recovery.sh"

workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT

export CROW_PLATFORM_DATA_DIR="$workspace/data"
export CROW_PLATFORM_CONFIG_DIR="$workspace/config"
export CROW_PLATFORM_BACKUP_DIR="$workspace/backups"
export CROW_SESSION_SECRET_PATH="$workspace/session-secret"
export CROW_AUTH_MODE=session
export CROW_PLATFORM_GID="$(id -g)"

proxy_data="$workspace/proxy-data"
proxy_config="$workspace/proxy-config"
mkdir -p "$CROW_PLATFORM_DATA_DIR/project-a" "$CROW_PLATFORM_CONFIG_DIR/audit"
mkdir -p "$proxy_data/caddy" "$proxy_config/caddy"
printf 'original-data\n' >"$CROW_PLATFORM_DATA_DIR/project-a/state.txt"
printf 'original-config\n' >"$CROW_PLATFORM_CONFIG_DIR/audit/events.jsonl"
printf 'original-proxy-data\n' >"$proxy_data/caddy/data.txt"
printf 'original-proxy-config\n' >"$proxy_config/caddy/config.txt"
printf '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n' >"$CROW_SESSION_SECRET_PATH"

capture_proxy_state() {
  local target="$1"
  tar -C "$proxy_data" -czf "$target/proxy-data.tar.gz" .
  tar -C "$proxy_config" -czf "$target/proxy-config.tar.gz" .
}

restore_proxy_state() {
  local source="$1"
  mv "$proxy_data" "$workspace/proxy-data-before-restore"
  mv "$proxy_config" "$workspace/proxy-config-before-restore"
  mkdir -p "$proxy_data" "$proxy_config"
  tar -xzf "$source/proxy-data.tar.gz" -C "$proxy_data"
  tar -xzf "$source/proxy-config.tar.gz" -C "$proxy_config"
}

mkdir -p "$CROW_PLATFORM_BACKUP_DIR"
archive="$CROW_PLATFORM_BACKUP_DIR/recovery.tar.gz"
create_recovery_archive "$archive" "test-sha"

test "$(recovery_git_sha "$archive")" = "test-sha"
test "$(stat -c '%a' "$archive")" = "600"
tar -tzf "$archive" | grep -qx 'platform.tar.gz'
tar -tzf "$archive" | grep -qx 'proxy-data.tar.gz'
tar -tzf "$archive" | grep -qx 'proxy-config.tar.gz'
tar -tzf "$archive" | grep -qx 'session-secret'

printf 'mutated-data\n' >"$CROW_PLATFORM_DATA_DIR/project-a/state.txt"
printf 'mutated-config\n' >"$CROW_PLATFORM_CONFIG_DIR/audit/events.jsonl"
printf 'mutated-proxy-data\n' >"$proxy_data/caddy/data.txt"
printf 'mutated-proxy-config\n' >"$proxy_config/caddy/config.txt"
printf 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff\n' >"$CROW_SESSION_SECRET_PATH"
printf 'extra\n' >"$CROW_PLATFORM_DATA_DIR/extra.txt"

restore_recovery_archive "$archive"

test "$(<"$CROW_PLATFORM_DATA_DIR/project-a/state.txt")" = "original-data"
test "$(<"$CROW_PLATFORM_CONFIG_DIR/audit/events.jsonl")" = "original-config"
test "$(<"$proxy_data/caddy/data.txt")" = "original-proxy-data"
test "$(<"$proxy_config/caddy/config.txt")" = "original-proxy-config"
test "$(tr -d '\r\n' <"$CROW_SESSION_SECRET_PATH")" = \
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
test ! -e "$CROW_PLATFORM_DATA_DIR/extra.txt"

echo "recovery archive round-trip passed"
