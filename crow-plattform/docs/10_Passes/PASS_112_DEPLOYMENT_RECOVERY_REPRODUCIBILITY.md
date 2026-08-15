# Pass 112 — Deployment recovery and reproducibility

## Scope

Pass 112 builds on the merged Pass 111 Debian bootstrap. It adds a recovery archive that carries the
state required to re-establish a session-mode Platform deployment and introduces recovery-gated
upgrade/rollback commands without replacing the older Pass 109 operational scripts before this pass
has been verified.

## Recovery archive contract

`deploy/recovery-backup.sh` creates a cold recovery archive containing:

- the existing SHA-256 protected Platform data/config archive;
- Caddy `/data` state, including internal-CA/certificate material when present;
- Caddy `/config` state;
- the external session-secret when session authentication is active;
- source Git SHA and recovery metadata;
- SHA-256 checksums for every recovery payload.

The archive is written with mode `0600` because it is a secret-bearing disaster-recovery artifact.
`deploy/recovery-restore.sh` verifies the checksums before restoring state. Platform data/config use
the exact Pass 109 restore behavior. Caddy files are written back into the existing Compose volumes;
this pass does not recreate volume identities and does not delete unrelated extra Caddy-volume files.

## Recovery-gated upgrade

`deploy/recovery-upgrade.sh`:

1. requires a clean deployment checkout;
2. creates a full recovery archive before `git pull --ff-only`;
3. records the previous SHA and recovery archive path;
4. builds/starts the new stack;
5. accepts the upgrade only when both direct backend `/health` and HTTPS `/health` through Caddy pass;
6. on gate failure, resets to the previous SHA, restores the pre-upgrade recovery archive, rebuilds
   and requires both gates again.

Exit code `1` means the upgrade failed but the previous deployment passed both gates after recovery.
Exit code `2` means the recovery attempt could not re-establish both gates.

## Recovery-gated rollback

`deploy/recovery-rollback.sh` uses the previous SHA/archive pair recorded by the recovery upgrade, or
accepts an explicit `TARGET_SHA RECOVERY.tar.gz` pair. The recovery archive's embedded Git SHA must
match the resolved target commit.

Before changing the current deployment, rollback creates a safety recovery archive. If the requested
target fails backend or HTTPS health, the command attempts to restore the original SHA and safety
archive.

## Compatibility boundary

The Pass 109 `backup.sh`, `restore.sh`, `upgrade.sh` and `rollback.sh` commands remain unchanged in
this pass. They retain their older filesystem-only/backend-only semantics. The new `recovery-*`
commands are isolated until Pass 112 CI and review are green.

## Runtime reproducibility boundary

The Platform Dockerfile is pinned to the official `python:3.11.15-slim-trixie` multi-platform index
digest:

`sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93`

Every Platform image build also records the resolved Python environment in
`/app/crow-runtime-dependencies.txt` with `pip freeze --all`.

This improves base-image reproducibility and makes Python dependency drift auditable. It does not
claim a fully hash-locked PyPI dependency graph: the project dependency declarations still contain
version ranges. A resolver-generated, reviewed lock with hashes is deferred rather than inventing
versions without resolver evidence.

The Caddy service remains on the existing exact `2.11.4-alpine` tag because connector policy blocked
changes to `compose.yaml` during this pass. No stronger digest-pinning claim is made for that service.

## CI evidence requirement

The existing deployment-validation step now invokes `tests/deployment_recovery.sh`. The test uses only
temporary directories and local proxy-state stubs, and verifies:

- recovery archive Git-SHA metadata;
- archive mode `0600`;
- presence of Platform, Caddy and session-secret payloads;
- Platform data/config recovery;
- Caddy data/config recovery through the recovery helper contract;
- session-secret recovery;
- removal of extra Platform data through the existing exact Platform restore.

The existing CI `bash -n deploy/*.sh deploy/lib/*.sh ...` glob also syntax-checks the new deployment
commands. The existing Compose/Caddy smoke remains the end-to-end runtime gate for the Platform stack.

## Explicit non-goals

Pass 112 does not claim exact deletion of unrelated Caddy-volume files, a hash-locked PyPI dependency
graph, public ACME issuance, firewall automation, OIDC/SAML/MFA, or schema-aware database migrations.
