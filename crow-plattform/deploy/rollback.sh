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

default_file="$CROW_PLATFORM_CONFIG_DIR/deployment/previous-sha"
target_sha="${1:-}"
if [[ -z "$target_sha" ]]; then
  [[ -f "$default_file" ]] || { echo "No recorded previous SHA; pass a commit SHA explicitly." >&2; exit 1; }
  target_sha="$(<"$default_file")"
fi

git -C "$CROW_PLATFORM_REPO_ROOT" cat-file -e "$target_sha^{commit}"
current_sha="$(current_git_sha)"
git -C "$CROW_PLATFORM_REPO_ROOT" reset --hard "$target_sha"
compose up -d --build
wait_for_health
printf 'Rollback healthy: %s -> %s\n' "$current_sha" "$target_sha"
