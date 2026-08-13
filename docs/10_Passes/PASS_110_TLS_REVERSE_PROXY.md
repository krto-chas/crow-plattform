# Pass 110 — TLS reverse proxy

## Scope

Pass 110 adds an explicit HTTPS reverse-proxy boundary to the Debian deployment while preserving the
loopback backend endpoint for diagnostics.

The pass builds on Pass 109 and assumes its backup, status, upgrade and rollback tooling.

## Deployment contract

- `crow-platform` remains the application service on port 8080.
- Direct host publication remains loopback-only by default.
- `crow-proxy` uses the pinned `caddy:2.11.4-alpine` image.
- `CROW_PROXY_SITE` is the single hostname input.
- `CROW_COOKIE_SECURE=true` is the Compose default.
- Caddy forwards to `crow-platform:8080` on the Compose network.
- Caddy `/data` and `/config` are persisted in named Docker volumes.
- `deploy/status.sh` contains a separate HTTPS route check in addition to direct backend health.

## TLS modes

For public DNS names, Caddy automatic HTTPS can obtain and renew publicly trusted certificates when
DNS and TCP 80/443 reach the host.

For private/local names, Caddy uses its internal CA. Client trust of the Caddy root CA is explicit;
the container cannot install that trust into other devices.

## Backup boundary

Pass 109 filesystem backups still cover Platform data/config only. The Caddy named volumes survive
container recreation but are not yet included in that archive. This is documented rather than
claiming proxy trust-state backup coverage that has not been implemented.

## Upgrade boundary

Pass 109's `upgrade.sh` remains unchanged. Automatic upgrade rollback therefore still gates on the
backend `/health`; operators use `deploy/status.sh` after an operation to check the HTTPS route too.

## CI evidence requirement

This pass can only be described as verified when CI demonstrates on the exact PR head that:

1. existing Ruff, mypy, strict module typing, pytest, architecture and distribution gates pass;
2. deployment backup/restore validation remains green;
3. Compose parses the complete Platform + Caddy stack;
4. the stack start command succeeds and both services are reported by Compose;
5. direct backend `/health` responds;
6. the Platform container receives `CROW_COOKIE_SECURE=true`;
7. the running proxy reports Caddy v2.11.4.

The automated CI gate does not claim browser trust of Caddy's local CA or successful public ACME
issuance. HTTPS route behavior is additionally exposed through `deploy/status.sh` for the target host.

## Explicit non-goals

This pass does not claim public DNS configuration, public ACME issuance on the user's future hostname,
client trust-store installation, firewall configuration, WAF/CDN integration, OIDC/SAML/MFA, or
backup of the Caddy named volumes.
