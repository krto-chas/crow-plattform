# Pass 110 — TLS reverse proxy

## Scope

Pass 110 adds an explicit HTTPS reverse-proxy boundary to the Debian deployment while preserving the
loopback backend endpoint for diagnostics.

The pass is stacked on Pass 109 and assumes its backup, status, upgrade and rollback tooling.

## Deployment contract

- `crow-platform` remains the application service on port 8080.
- Direct host publication remains loopback-only by default.
- `crow-proxy` uses the pinned `caddy:2.11.4-alpine` image.
- `CROW_PROXY_SITE` is the single hostname input.
- `CROW_COOKIE_SECURE=true` is the Compose default.
- Caddy forwards to `crow-platform:8080` on the Compose network.
- Caddy `/data` and `/config` are persisted in named Docker volumes.
- `deploy/status.sh` verifies both direct backend health and the HTTPS route.

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

Pass 109's `upgrade.sh` remains unchanged because the connector refused a safe rewrite of the
existing destructive rollback script. Automatic upgrade rollback therefore still gates on backend
`/health`; operators use `deploy/status.sh` after the operation to verify the HTTPS route.

## CI evidence requirement

This pass can only be described as verified when CI demonstrates on the exact PR head that:

1. existing Ruff, mypy, strict module typing, pytest, architecture and distribution gates pass;
2. deployment backup/restore validation remains green;
3. Compose parses the complete Platform + Caddy stack;
4. both services start;
5. direct backend `/health` responds;
6. Caddy's local CA root can be retrieved from its persisted data volume;
7. HTTPS `/health` succeeds while validating against that CA root;
8. the Platform container receives `CROW_COOKIE_SECURE=true`;
9. the running proxy reports Caddy v2.11.4.

## Explicit non-goals

This pass does not claim public DNS configuration, public ACME issuance on the user's future hostname,
client trust-store installation, firewall configuration, WAF/CDN integration, OIDC/SAML/MFA, or
backup of the Caddy named volumes.
