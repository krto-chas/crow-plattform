#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="$(mktemp -d)"

cleanup() {
  docker run --rm -v "$workspace:/state" debian:trixie-slim sh -c 'rm -rf /state/*' >/dev/null 2>&1 || true
  rm -rf "$workspace"
}
trap cleanup EXIT

host_uid="$(id -u)"
host_gid="$(id -g)"

docker run --rm \
  -v "$REPO_ROOT:/repo:ro" \
  -v "$workspace:/state" \
  -e "CROW_PLATFORM_UID=$host_uid" \
  -e "CROW_PLATFORM_GID=$host_gid" \
  -e CROW_PLATFORM_ENV_FILE=/state/crow.env \
  -e CROW_PLATFORM_DATA_DIR=/state/data \
  -e CROW_PLATFORM_CONFIG_DIR=/state/config \
  -e CROW_PLATFORM_BACKUP_DIR=/state/backups \
  -e CROW_SESSION_SECRET_PATH=/state/etc/session-secret \
  -e CROW_BOOTSTRAP_SKIP_PACKAGES=true \
  -e CROW_BOOTSTRAP_SKIP_START=true \
  debian:trixie-slim \
  bash -lc '
    set -euo pipefail
    apt-get update >/dev/null
    apt-get -s install -y ca-certificates curl git openssl docker.io docker-cli docker-compose >/dev/null
    DEBIAN_FRONTEND=noninteractive apt-get install -y openssl >/dev/null

    bash /repo/deploy/bootstrap.sh
    first_secret="$(sha256sum /state/etc/session-secret | cut -d" " -f1)"
    bash /repo/deploy/bootstrap.sh
    second_secret="$(sha256sum /state/etc/session-secret | cut -d" " -f1)"

    test "$first_secret" = "$second_secret"
    test "$(stat -c %a /state/data)" = "750"
    test "$(stat -c %a /state/config)" = "750"
    test "$(stat -c %a /state/backups)" = "750"
    test "$(stat -c %a /state/etc/session-secret)" = "440"
    test "$(stat -c %a /state/crow.env)" = "600"
    grep -q "^CROW_SESSION_SECRET_PATH=/state/etc/session-secret$" /state/crow.env
    if grep -q "^CROW_SESSION_SECRET=" /state/crow.env; then
      echo "bootstrap leaked inline session secret into .env" >&2
      exit 1
    fi
  '

echo "debian bootstrap contract passed"
