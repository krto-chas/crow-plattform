#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="$REPO_ROOT/requirements/runtime-direct.lock"
IMAGE_TAG="crow-platform-pass113-ci:${GITHUB_SHA:-local}"
container_id=""
inventory="$(mktemp)"
runtime_root="$(mktemp -d)"

cleanup() {
  if [[ -n "$container_id" ]]; then
    docker rm -f "$container_id" >/dev/null 2>&1 || true
  fi
  docker image rm -f "$IMAGE_TAG" >/dev/null 2>&1 || true
  rm -f "$inventory"
  rm -rf "$runtime_root"
}
trap cleanup EXIT

docker compose \
  -f "$REPO_ROOT/compose.yaml" \
  -f "$REPO_ROOT/compose.locked.yaml" \
  config >/dev/null

docker build \
  --file "$REPO_ROOT/deploy/Dockerfile.locked" \
  --tag "$IMAGE_TAG" \
  "$REPO_ROOT"

container_id="$(docker create "$IMAGE_TAG")"
docker cp "$container_id:/app/crow-runtime-dependencies.txt" "$inventory"
docker rm -f "$container_id" >/dev/null
container_id=""

while IFS= read -r raw_line; do
  line="${raw_line%%#*}"
  line="$(printf '%s' "$line" | xargs)"
  [[ -n "$line" ]] || continue
  grep -Fqx "$line" "$inventory" || {
    echo "Locked dependency missing from built image: $line" >&2
    exit 1
  }
done <"$LOCK_FILE"

mkdir -p "$runtime_root/data" "$runtime_root/config"
chmod 0777 "$runtime_root/data" "$runtime_root/config"
docker run --rm \
  --user 1000:1000 \
  --env CROW_PLATFORM_DATA_ROOT=/srv/crow-data/platform \
  --env CROW_PLATFORM_CONFIG_ROOT=/srv/crow-config/platform \
  --env CROW_AUTH_MODE=environment \
  --env CROW_MODE=local \
  --volume "$runtime_root/data:/srv/crow-data/platform" \
  --volume "$runtime_root/config:/srv/crow-config/platform" \
  "$IMAGE_TAG" \
  python -c "import crow_workbench.shell; print('non-root platform import passed')"

echo "locked runtime image dependency verification passed"
