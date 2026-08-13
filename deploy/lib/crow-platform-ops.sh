#!/usr/bin/env bash

set -euo pipefail

CROW_PLATFORM_REPO_ROOT="${CROW_PLATFORM_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
CROW_PLATFORM_ENV_FILE="${CROW_PLATFORM_ENV_FILE:-$CROW_PLATFORM_REPO_ROOT/.env}"

load_platform_env() {
  if [[ -f "$CROW_PLATFORM_ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$CROW_PLATFORM_ENV_FILE"
    set +a
  fi

  CROW_PLATFORM_DATA_DIR="${CROW_PLATFORM_DATA_DIR:-/srv/crow-data/platform}"
  CROW_PLATFORM_CONFIG_DIR="${CROW_PLATFORM_CONFIG_DIR:-/srv/crow-config/platform}"
  CROW_PLATFORM_BACKUP_DIR="${CROW_PLATFORM_BACKUP_DIR:-/srv/crow-backups/platform}"
  CROW_PLATFORM_PORT="${CROW_PLATFORM_PORT:-8080}"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1" >&2
    return 1
  }
}

assert_safe_directory() {
  local path="$1"
  if [[ -z "$path" || "$path" == "/" ]]; then
    echo "Refusing unsafe directory: '$path'" >&2
    return 1
  fi
}

compose() {
  docker compose --project-directory "$CROW_PLATFORM_REPO_ROOT" --env-file "$CROW_PLATFORM_ENV_FILE" "$@"
}

service_is_running() {
  local container_id
  container_id="$(compose ps -q crow-platform 2>/dev/null || true)"
  [[ -n "$container_id" ]] || return 1
  [[ "$(docker inspect -f '{{.State.Running}}' "$container_id" 2>/dev/null || true)" == "true" ]]
}

wait_for_health() {
  local attempts="${1:-30}"
  local url="http://127.0.0.1:${CROW_PLATFORM_PORT}/health"
  local attempt
  for attempt in $(seq 1 "$attempts"); do
    if curl --fail --silent "$url" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  echo "Health check failed: $url" >&2
  return 1
}

current_git_sha() {
  git -C "$CROW_PLATFORM_REPO_ROOT" rev-parse HEAD
}

require_clean_git() {
  if [[ -n "$(git -C "$CROW_PLATFORM_REPO_ROOT" status --porcelain)" ]]; then
    echo "Deployment checkout has local changes; refusing operation." >&2
    return 1
  fi
}

create_backup_archive() (
  local destination="$1"
  local source_sha="$2"
  local workspace

  load_platform_env
  assert_safe_directory "$CROW_PLATFORM_DATA_DIR"
  assert_safe_directory "$CROW_PLATFORM_CONFIG_DIR"
  mkdir -p "$CROW_PLATFORM_BACKUP_DIR"
  workspace="$(mktemp -d)"
  trap 'rm -rf "$workspace"' EXIT

  tar --numeric-owner -C "$CROW_PLATFORM_DATA_DIR" -czf "$workspace/data.tar.gz" .
  tar --numeric-owner -C "$CROW_PLATFORM_CONFIG_DIR" -czf "$workspace/config.tar.gz" .
  printf 'git_sha=%s\ncreated_utc=%s\n' "$source_sha" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$workspace/metadata.env"
  (
    cd "$workspace"
    sha256sum data.tar.gz config.tar.gz metadata.env >SHA256SUMS
    tar -czf "$destination" data.tar.gz config.tar.gz metadata.env SHA256SUMS
  )
)

restore_backup_archive() (
  local archive="$1"
  local workspace

  load_platform_env
  assert_safe_directory "$CROW_PLATFORM_DATA_DIR"
  assert_safe_directory "$CROW_PLATFORM_CONFIG_DIR"
  workspace="$(mktemp -d)"
  trap 'rm -rf "$workspace"' EXIT

  tar -xzf "$archive" -C "$workspace"
  (
    cd "$workspace"
    sha256sum -c SHA256SUMS
  )

  mkdir -p "$CROW_PLATFORM_DATA_DIR" "$CROW_PLATFORM_CONFIG_DIR"
  find "$CROW_PLATFORM_DATA_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  find "$CROW_PLATFORM_CONFIG_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  tar -xzf "$workspace/data.tar.gz" -C "$CROW_PLATFORM_DATA_DIR"
  tar -xzf "$workspace/config.tar.gz" -C "$CROW_PLATFORM_CONFIG_DIR"
)
