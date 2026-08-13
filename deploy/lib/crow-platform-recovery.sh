#!/usr/bin/env bash

set -euo pipefail

capture_proxy_state() {
  local workspace="$1"
  compose run --rm -T --no-deps --entrypoint sh crow-proxy \
    -c 'tar -czf - -C /data .' >"$workspace/proxy-data.tar.gz"
  compose run --rm -T --no-deps --entrypoint sh crow-proxy \
    -c 'tar -czf - -C /config .' >"$workspace/proxy-config.tar.gz"
}

restore_proxy_state() {
  local workspace="$1"
  compose run --rm -T --no-deps --entrypoint sh crow-proxy \
    -c 'tar -xzf - -C /data' <"$workspace/proxy-data.tar.gz"
  compose run --rm -T --no-deps --entrypoint sh crow-proxy \
    -c 'tar -xzf - -C /config' <"$workspace/proxy-config.tar.gz"
}

validate_recovery_members() {
  local archive="$1"
  local member
  while IFS= read -r member; do
    case "$member" in
      platform.tar.gz | proxy-data.tar.gz | proxy-config.tar.gz | session-secret | metadata.env | SHA256SUMS) ;;
      *)
        echo "Unexpected recovery member: $member" >&2
        return 1
        ;;
    esac
  done < <(tar -tzf "$archive")
}

recovery_git_sha() {
  local archive="$1"
  validate_recovery_members "$archive"
  tar -xOzf "$archive" metadata.env | sed -n 's/^git_sha=//p' | tail -n 1
}

create_recovery_archive() (
  local destination="$1"
  local source_sha="$2"
  local workspace

  load_platform_env
  workspace="$(mktemp -d)"
  trap 'rm -rf "$workspace"' EXIT

  create_backup_archive "$workspace/platform.tar.gz" "$source_sha"
  capture_proxy_state "$workspace"

  if [[ "$CROW_AUTH_MODE" == "session" ]]; then
    [[ -s "${CROW_SESSION_SECRET_PATH:-}" ]] || {
      echo "Session secret is required for a recoverable session-mode backup" >&2
      return 1
    }
    cp "$CROW_SESSION_SECRET_PATH" "$workspace/session-secret"
    chmod 0400 "$workspace/session-secret"
  fi

  printf 'recovery_format_version=1\ngit_sha=%s\ncreated_utc=%s\n' \
    "$source_sha" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$workspace/metadata.env"

  (
    cd "$workspace"
    if [[ -f session-secret ]]; then
      sha256sum platform.tar.gz proxy-data.tar.gz proxy-config.tar.gz session-secret metadata.env >SHA256SUMS
      tar -czf "$destination" platform.tar.gz proxy-data.tar.gz proxy-config.tar.gz session-secret metadata.env SHA256SUMS
    else
      sha256sum platform.tar.gz proxy-data.tar.gz proxy-config.tar.gz metadata.env >SHA256SUMS
      tar -czf "$destination" platform.tar.gz proxy-data.tar.gz proxy-config.tar.gz metadata.env SHA256SUMS
    fi
  )
  chmod 0600 "$destination"
)

restore_recovery_archive() (
  local archive="$1"
  local workspace
  local secret_parent

  load_platform_env
  validate_recovery_members "$archive"
  workspace="$(mktemp -d)"
  trap 'rm -rf "$workspace"' EXIT
  tar -xzf "$archive" -C "$workspace"
  (
    cd "$workspace"
    sha256sum -c SHA256SUMS
  )

  restore_backup_archive "$workspace/platform.tar.gz"

  if [[ -f "$workspace/session-secret" ]]; then
    secret_parent="$(dirname "$CROW_SESSION_SECRET_PATH")"
    assert_safe_directory "$secret_parent"
    mkdir -p "$secret_parent"
    install -m 0440 "$workspace/session-secret" "$CROW_SESSION_SECRET_PATH"
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
      chown 0:"${CROW_PLATFORM_GID:-1000}" "$CROW_SESSION_SECRET_PATH"
    fi
  elif [[ "$CROW_AUTH_MODE" == "session" ]]; then
    echo "Recovery archive is missing the session secret" >&2
    return 1
  fi

  restore_proxy_state "$workspace"
)
