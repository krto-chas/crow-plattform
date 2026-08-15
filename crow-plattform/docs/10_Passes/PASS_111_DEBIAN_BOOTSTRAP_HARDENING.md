# Pass 111 — Debian bootstrap hardening

## Scope

Pass 111 turns the existing Pass 108–110 Compose deployment into an idempotent fresh-host bootstrap
for Debian 13 or newer without changing the module deployment model.

## Host bootstrap contract

`deploy/bootstrap.sh` must refuse unsupported hosts, install the Debian runtime packages, enable
Docker, create persistent Platform paths, create or preserve `.env`, create a session-secret file
outside the repository, validate Compose, start the complete stack and gate completion on backend and
HTTPS health.

## Session-secret boundary

Bootstrap sets `CROW_SESSION_SECRET_PATH`. Compose mounts that host path read-only into the Platform
container as `/run/secrets/crow_session_secret`, and the application reads it through
`CROW_SESSION_SECRET_FILE`.

Direct `CROW_SESSION_SECRET` remains a compatibility fallback for development and the existing CI
smoke. Bootstrap-generated `.env` files do not contain the secret value.

## CI evidence requirement

The existing deployment validation invokes `tests/deployment_bootstrap.sh`. It runs in
`debian:trixie-slim` and checks package resolution, fresh-host preparation, repeat-run secret
stability, directory permissions, `.env` permissions, secret permissions and absence of an inline
secret in the generated `.env`.

`pytest` separately verifies file-backed session authentication. The existing Compose/Caddy smoke
remains the end-to-end runtime gate.

## Explicit non-goals

This pass does not add Caddy-volume backup, secret-file backup policy, schema/data migration rollback,
HTTPS gating inside `upgrade.sh`, public DNS, firewall configuration, public ACME proof, OIDC/SAML or
MFA.
