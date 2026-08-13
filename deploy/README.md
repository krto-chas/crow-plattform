# Crow Platform Debian deployment

This is the reproducible Debian deployment path for the complete Crow Platform stack.
It follows the same container/Compose pattern as Crow Health while preserving Platform-specific
identity, configuration and module boundaries.

## Runtime contract

The deployment contains two runtime services:

1. `crow-platform`: the Platform backbone plus every first-party module declared in
   `modules/module_layout_manifest.json`, installed in dependency order;
2. `crow-proxy`: Caddy 2.11.4, terminating HTTPS and forwarding requests to
   `crow-platform:8080` on the private Compose network.

The direct Platform host port remains loopback-only by default and is an operational diagnostic
path. Browser traffic should use the HTTPS proxy.

Persistent Platform state remains:

- data: `/srv/crow-data/platform`;
- config: `/srv/crow-config/platform`;
- backups: `/srv/crow-backups/platform`.

Caddy certificate/configuration state is persisted in the Compose volumes `crow_proxy_data` and
`crow_proxy_config`. These volumes survive container recreation but are outside the Pass 109
filesystem backup archive; sites using Caddy's internal CA must back up/export that trust state
separately until proxy-volume backup is added.

## First installation

```bash
cp deploy/crow-platform.env.example .env
openssl rand -hex 32
```

Put the generated value in `.env` as `CROW_SESSION_SECRET`, then create the Platform persistent
paths with ownership matching `CROW_PLATFORM_UID`/`CROW_PLATFORM_GID`.

```bash
sudo install -d -m 0750 -o 1000 -g 1000 /srv/crow-data/platform
sudo install -d -m 0750 -o 1000 -g 1000 /srv/crow-config/platform
sudo install -d -m 0750 -o 1000 -g 1000 /srv/crow-backups/platform
docker compose up -d --build
```

Direct process health remains available on loopback:

```bash
curl http://127.0.0.1:8080/health
```

## HTTPS modes

`CROW_PROXY_SITE` controls the Caddy site name. The shipped default is `crow.localhost`.

For a public DNS name, set `CROW_PROXY_SITE` to that name, point its A/AAAA record to the Debian
host, set `CROW_PROXY_BIND_ADDRESS` to the intended reachable address (or `0.0.0.0`), and allow or
forward TCP 80 and TCP/UDP 443. Caddy then manages HTTPS certificates and redirects HTTP to HTTPS.

For a private/LAN hostname, set a resolvable private name and intentionally expose Caddy on the LAN.
Caddy uses its internal CA for names that cannot receive publicly trusted certificates. Client
machines must trust that CA root before browsers consider the connection trusted. Caddy running in a
container cannot silently install trust on other devices.

Export the local CA root for controlled client installation with:

```bash
docker compose cp crow-proxy:/data/caddy/pki/authorities/local/root.crt ./crow-platform-local-ca.crt
```

Distribute only the root certificate, never the CA private key.

## Session boundary

Compose defaults to `CROW_AUTH_MODE=session` and `CROW_COOKIE_SECURE=true`; the session secret is
mandatory. The direct HTTP backend is therefore diagnostic only, while browser login/session traffic
uses HTTPS through Caddy.

Caddy's standard reverse-proxy behavior supplies `X-Forwarded-For`, `X-Forwarded-Proto` and
`X-Forwarded-Host` to the backend.

## Bootstrap the first administrator

```bash
docker compose exec crow-platform crow-user admin --customer platform --role platform-admin
```

## Operational status and logs

```bash
./deploy/status.sh
```

The status command reports the Git SHA, both services, direct backend health and the HTTPS route.
Docker's local logs are bounded for both services.

```bash
docker compose logs --tail=200 crow-platform crow-proxy
docker compose logs -f crow-platform crow-proxy
```

## Consistent backup and restore

Pass 109's cold Platform backup/restore remains unchanged:

```bash
./deploy/backup.sh
./deploy/restore.sh /srv/crow-backups/platform/crow-platform-YYYYMMDDTHHMMSSZ.tar.gz
```

The archive covers Platform data/config and verifies SHA-256 checksums before restore. It does not yet
archive the two Docker-managed Caddy volumes.

## Guarded upgrade and rollback

Pass 109's guarded upgrade and code rollback commands remain the deployment mechanism:

```bash
./deploy/upgrade.sh
./deploy/rollback.sh
```

After an operation, use `./deploy/status.sh` to verify both direct backend health and HTTPS routing.
The upgrade script itself still gates on backend `/health`; moving the HTTPS route into its automatic
rollback gate is intentionally deferred because the current connector could not safely rewrite the
existing destructive rollback script in this pass.
