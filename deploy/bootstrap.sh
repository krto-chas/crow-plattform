#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export CROW_PLATFORM_ENV_FILE="${CROW_PLATFORM_ENV_FILE:-$REPO_ROOT/.env}"
ENV_FILE="$CROW_PLATFORM_ENV_FILE"

is_true() {
  case "${1:-}" in
    1 | true | TRUE | yes | YES) return 0 ;;
    *) return 1 ;;
  esac
}

fail() {
  echo "$*" >&2
  exit 1
}

require_root() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || fail "Run bootstrap as root, for example: sudo ./deploy/bootstrap.sh"
}

require_supported_debian() {
  [[ -r /etc/os-release ]] || fail "Cannot identify the operating system: /etc/os-release is missing"
  # shellcheck disable=SC1091
  source /etc/os-release
  [[ "${ID:-}" == "debian" ]] || fail "Pass 111 bootstrap supports Debian hosts only"
  local major="${VERSION_ID%%.*}"
  [[ "$major" =~ ^[0-9]+$ ]] || fail "Cannot parse Debian VERSION_ID=${VERSION_ID:-unknown}"
  (( major >= 13 )) || fail "Pass 111 requires Debian 13 (trixie) or newer"
}

install_host_dependencies() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl git openssl docker.io docker-cli docker-compose
  systemctl enable --now docker
}

load_existing_env() {
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi
}

write_fresh_env() {
  umask 077
  cat >"$ENV_FILE" <<EOF
# Backend diagnostic exposure. Keep loopback-only; browsers should use the HTTPS proxy.
CROW_PLATFORM_BIND_ADDRESS=${CROW_PLATFORM_BIND_ADDRESS}
CROW_PLATFORM_PORT=${CROW_PLATFORM_PORT}

# HTTPS reverse-proxy exposure. Keep loopback-only until LAN/public exposure is intentional.
CROW_PROXY_BIND_ADDRESS=${CROW_PROXY_BIND_ADDRESS}
CROW_PROXY_HTTP_PORT=${CROW_PROXY_HTTP_PORT}
CROW_PROXY_HTTPS_PORT=${CROW_PROXY_HTTPS_PORT}
CROW_PROXY_SITE=${CROW_PROXY_SITE}

# Numeric host UID/GID used for writes to mounted Platform directories.
CROW_PLATFORM_UID=${CROW_PLATFORM_UID}
CROW_PLATFORM_GID=${CROW_PLATFORM_GID}

# Persistent host directories.
CROW_PLATFORM_DATA_DIR=${CROW_PLATFORM_DATA_DIR}
CROW_PLATFORM_CONFIG_DIR=${CROW_PLATFORM_CONFIG_DIR}
CROW_PLATFORM_BACKUP_DIR=${CROW_PLATFORM_BACKUP_DIR}

# Host path to the session secret. The secret value itself is never stored in .env.
CROW_SESSION_SECRET_PATH=${CROW_SESSION_SECRET_PATH}

# Bounded local Docker logging.
CROW_PLATFORM_LOG_MAX_SIZE=${CROW_PLATFORM_LOG_MAX_SIZE}
CROW_PLATFORM_LOG_MAX_FILES=${CROW_PLATFORM_LOG_MAX_FILES}
CROW_PROXY_LOG_MAX_SIZE=${CROW_PROXY_LOG_MAX_SIZE}
CROW_PROXY_LOG_MAX_FILES=${CROW_PROXY_LOG_MAX_FILES}

# Debian Compose deployment runs the Platform in session mode behind HTTPS.
CROW_AUTH_MODE=${CROW_AUTH_MODE}
CROW_COOKIE_SECURE=${CROW_COOKIE_SECURE}
EOF
  chown "$CROW_PLATFORM_UID:$CROW_PLATFORM_GID" "$ENV_FILE"
  chmod 0600 "$ENV_FILE"
}

ensure_env_key() {
  local key="$1"
  local value="$2"
  if ! grep -q "^${key}=" "$ENV_FILE"; then
    printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
  fi
}

migrate_inline_secret() {
  [[ -f "$ENV_FILE" ]] || return 0
  local inline_secret=""
  inline_secret="$(grep '^CROW_SESSION_SECRET=' "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  [[ -n "$inline_secret" ]] || return 0

  if [[ -s "$CROW_SESSION_SECRET_PATH" ]]; then
    local existing_secret
    existing_secret="$(tr -d '\r\n' <"$CROW_SESSION_SECRET_PATH")"
    [[ "$existing_secret" == "$inline_secret" ]] || fail \
      "Existing session-secret file differs from CROW_SESSION_SECRET in $ENV_FILE"
  else
    printf '%s\n' "$inline_secret" >"$CROW_SESSION_SECRET_PATH"
  fi

  local temporary
  temporary="$(mktemp "${ENV_FILE}.XXXXXX")"
  awk '!/^CROW_SESSION_SECRET=/' "$ENV_FILE" >"$temporary"
  chown "$CROW_PLATFORM_UID:$CROW_PLATFORM_GID" "$temporary"
  chmod 0600 "$temporary"
  mv "$temporary" "$ENV_FILE"
  unset CROW_SESSION_SECRET
}

prepare_persistent_state() {
  install -d -m 0750 -o "$CROW_PLATFORM_UID" -g "$CROW_PLATFORM_GID" \
    "$CROW_PLATFORM_DATA_DIR" "$CROW_PLATFORM_CONFIG_DIR" "$CROW_PLATFORM_BACKUP_DIR"

  local secret_dir
  secret_dir="$(dirname "$CROW_SESSION_SECRET_PATH")"
  install -d -m 0750 -o 0 -g "$CROW_PLATFORM_GID" "$secret_dir"

  migrate_inline_secret

  if [[ ! -s "$CROW_SESSION_SECRET_PATH" ]]; then
    umask 027
    openssl rand -hex 32 >"$CROW_SESSION_SECRET_PATH"
  fi

  chown 0:"$CROW_PLATFORM_GID" "$CROW_SESSION_SECRET_PATH"
  chmod 0440 "$CROW_SESSION_SECRET_PATH"

  local secret_value
  secret_value="$(tr -d '\r\n' <"$CROW_SESSION_SECRET_PATH")"
  (( ${#secret_value} >= 32 )) || fail "Session secret must contain at least 32 characters"
}

require_root
require_supported_debian
load_existing_env

CROW_PLATFORM_UID="${CROW_PLATFORM_UID:-${SUDO_UID:-1000}}"
CROW_PLATFORM_GID="${CROW_PLATFORM_GID:-${SUDO_GID:-1000}}"
CROW_PLATFORM_BIND_ADDRESS="${CROW_PLATFORM_BIND_ADDRESS:-127.0.0.1}"
CROW_PLATFORM_PORT="${CROW_PLATFORM_PORT:-8080}"
CROW_PROXY_BIND_ADDRESS="${CROW_PROXY_BIND_ADDRESS:-127.0.0.1}"
CROW_PROXY_HTTP_PORT="${CROW_PROXY_HTTP_PORT:-80}"
CROW_PROXY_HTTPS_PORT="${CROW_PROXY_HTTPS_PORT:-443}"
CROW_PROXY_SITE="${CROW_PROXY_SITE:-crow.localhost}"
CROW_PLATFORM_DATA_DIR="${CROW_PLATFORM_DATA_DIR:-/srv/crow-data/platform}"
CROW_PLATFORM_CONFIG_DIR="${CROW_PLATFORM_CONFIG_DIR:-/srv/crow-config/platform}"
CROW_PLATFORM_BACKUP_DIR="${CROW_PLATFORM_BACKUP_DIR:-/srv/crow-backups/platform}"
CROW_SESSION_SECRET_PATH="${CROW_SESSION_SECRET_PATH:-/etc/crow-platform/session-secret}"
CROW_PLATFORM_LOG_MAX_SIZE="${CROW_PLATFORM_LOG_MAX_SIZE:-10m}"
CROW_PLATFORM_LOG_MAX_FILES="${CROW_PLATFORM_LOG_MAX_FILES:-5}"
CROW_PROXY_LOG_MAX_SIZE="${CROW_PROXY_LOG_MAX_SIZE:-10m}"
CROW_PROXY_LOG_MAX_FILES="${CROW_PROXY_LOG_MAX_FILES:-5}"
CROW_AUTH_MODE="${CROW_AUTH_MODE:-session}"
CROW_COOKIE_SECURE="${CROW_COOKIE_SECURE:-true}"

if ! is_true "${CROW_BOOTSTRAP_SKIP_PACKAGES:-false}"; then
  install_host_dependencies
fi

command -v openssl >/dev/null 2>&1 || fail "Required command not found: openssl"

if [[ ! -f "$ENV_FILE" ]]; then
  write_fresh_env
else
  ensure_env_key "CROW_SESSION_SECRET_PATH" "$CROW_SESSION_SECRET_PATH"
  chown "$CROW_PLATFORM_UID:$CROW_PLATFORM_GID" "$ENV_FILE"
  chmod 0600 "$ENV_FILE"
fi

prepare_persistent_state

if is_true "${CROW_BOOTSTRAP_SKIP_START:-false}"; then
  echo "Crow Platform host state prepared; service start skipped by CROW_BOOTSTRAP_SKIP_START"
  exit 0
fi

command -v docker >/dev/null 2>&1 || fail "Required command not found: docker"
command -v curl >/dev/null 2>&1 || fail "Required command not found: curl"
docker compose version >/dev/null

# shellcheck source=deploy/lib/crow-platform-ops.sh
source "$SCRIPT_DIR/lib/crow-platform-ops.sh"
load_platform_env
compose config >/dev/null
compose up -d --build
wait_for_health 60
wait_for_proxy_route 60

echo "Crow Platform bootstrap completed"
echo "HTTPS site: https://${CROW_PROXY_SITE}:${CROW_PROXY_HTTPS_PORT}"
echo "Create the first administrator with: docker compose exec crow-platform crow-user admin --customer platform --role platform-admin"
