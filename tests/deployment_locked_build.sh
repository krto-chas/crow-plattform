#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="$REPO_ROOT/requirements/runtime-direct.lock"
IMAGE_TAG="crow-platform-pass113-ci:${GITHUB_SHA:-local}"
container_id=""
inventory="$(mktemp)"

cleanup() {
  if [[ -n "$container_id" ]]; then
    docker rm -f "$container_id" >/dev/null 2>&1 || true
  fi
  docker image rm -f "$IMAGE_TAG" >/dev/null 2>&1 || true
  rm -f "$inventory"
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

while IFS= read -r raw_line; do
  line="${raw_line%%#*}"
  line="$(printf '%s' "$line" | xargs)"
  [[ -n "$line" ]] || continue
  grep -Fqx "$line" "$inventory" || {
    echo "Locked dependency missing from built image: $line" >&2
    exit 1
  }
done <"$LOCK_FILE"

echo "locked runtime image dependency verification passed"
