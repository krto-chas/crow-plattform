# Crow Platform Debian deployment

This is the reproducible Debian deployment path for the complete Crow Platform stack. It follows the
same container/Compose pattern as Crow Health while preserving Platform-specific identity,
configuration and module boundaries.

## Supported host

Pass 111 targets Debian 13 (trixie) or newer with systemd and the standard Debian APT repositories.
The bootstrap installs `docker.io`, `docker-cli`, Docker Compose v2 (`docker-compose`), `git`,
`curl`, `openssl` and CA certificates from Debian packages.

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
- backups: `/srv/crow-backups/platform`;
- session secret: `/etc/crow-platform/session-secret` by default.

Caddy certificate/configuration state is persisted in the Compose volumes `crow_proxy_data` and
`crow_proxy_config`. These volumes survive container recreation but are outside the Pass 109
filesystem backup archive; sites using Caddy's internal CA must back up/export that trust state
separately until proxy-volume backup is added.

## First installation

From a clean Debian host with this repository checked out:

```bash
sudo bash ./deploy/bootstrap.sh
```

The bootstrap is idempotent. It:

- validates the Debian host version;
- installs the required Debian packages and enables Docker;
- creates the Platform data/config/backup directories with the configured numeric UID/GID;
- creates `.env` if it does not already exist;
- creates a 256-bit random session secret outside the repository;
- validates Compose;
- builds and starts the complete Platform + Caddy stack;
- waits for direct backend health and the HTTPS proxy route.

The secret value is not stored in a fresh `.env`. Bootstrap sets `CROW_SESSION_SECRET_PATH`, Compose
mounts that host file read-only at `/run/secrets/crow_session_secret`, and the application reads it
through `CROW_SESSION_SECRET_FILE`.

For an existing Pass 110 deployment, bootstrap can migrate a non-empty `CROW_SESSION_SECRET=` value
from `.env` into the secret file. It refuses migration if an existing secret file contains a
different value.

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

Compose defaults to `CROW_AUTH_MODE=session` and `CROW_COOKIE_SECURE=true`. The Debian bootstrap
configures the file-backed secret path and leaves the direct HTTP backend as a diagnostic route;
browser login/session traffic uses HTTPS through Caddy.

The application and Compose definition still accept `CROW_SESSION_SECRET` as a compatibility fallback
for development and the pre-Pass-111 CI smoke. A bootstrap-generated deployment does not put the
secret value in `.env`.

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
archive the two Docker-managed Caddy volumes or the external session-secret file.

## Guarded upgrade and rollback

Pass 109's guarded upgrade and code rollback commands remain the deployment mechanism:

```bash
./deploy/upgrade.sh
./deploy/rollback.sh
```

After an operation, use `./deploy/status.sh` to verify both direct backend health and HTTPS routing.
The upgrade script itself still gates on backend `/health`; HTTPS upgrade gating and full
proxy/secret disaster-recovery coverage are deferred to the next deployment-recovery pass.
