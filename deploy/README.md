# Crow Platform Debian deployment

This is the reproducible Debian deployment path for the complete Crow Platform stack.
It follows the same container/Compose pattern as Crow Health while preserving Platform-specific
identity, configuration and module boundaries.

## Runtime contract

The container image installs:

1. the Crow Platform backbone with export support;
2. every first-party module declared in `modules/module_layout_manifest.json`, in dependency order.

The image build uses `crow-install-modules --root /app`. A future first-party module therefore
requires its package plus its canonical manifest entry; the Debian host does not gain another
module-specific installation command.

Persistent state is split into two host mounts:

- data: `/srv/crow-data/platform` -> projects, uploads and module runtime data;
- config: `/srv/crow-config/platform` -> users, customer entitlements and administrative audit;
- backups: `/srv/crow-backups/platform` -> cold state archives with checksums and deployment SHA.

The application receives the first two locations through `CROW_PLATFORM_DATA_ROOT` and
`CROW_PLATFORM_CONFIG_ROOT`. Local source execution remains compatible with the historical
`.crow-workbench` default when those variables are absent.

## First installation

Install Docker Engine with the Docker Compose plugin, clone the repository, then create the local
environment file:

```bash
cp deploy/crow-platform.env.example .env
```

Generate a session secret and place it in `.env` as `CROW_SESSION_SECRET`:

```bash
openssl rand -hex 32
```

Create the persistent directories. The owner must match `CROW_PLATFORM_UID` and
`CROW_PLATFORM_GID` from `.env`:

```bash
sudo install -d -m 0750 -o 1000 -g 1000 /srv/crow-data/platform
sudo install -d -m 0750 -o 1000 -g 1000 /srv/crow-config/platform
sudo install -d -m 0750 -o 1000 -g 1000 /srv/crow-backups/platform
```

Build and start the Platform:

```bash
docker compose up -d --build
```

Verify the process-level health endpoint:

```bash
curl http://127.0.0.1:8080/health
```

## Bootstrap the first administrator

The `crow-user` CLI uses `CROW_PLATFORM_CONFIG_ROOT` by default, so it writes directly to the
mounted configuration volume inside the container:

```bash
docker compose exec crow-platform crow-user admin --customer platform --role platform-admin
```

The command prompts for a password and confirmation. Password material is stored using the
existing scrypt user-record implementation; plaintext passwords are not written to disk.

## Session and network mode

Compose enables `CROW_AUTH_MODE=session`. `CROW_SESSION_SECRET` is mandatory and must contain at
least 32 characters.

Host exposure remains loopback-only by default. Change `CROW_PLATFORM_BIND_ADDRESS` only when LAN
exposure is intentional. `CROW_COOKIE_SECURE=false` is suitable only for the current internal
plain-HTTP path; set it to `true` when the browser reaches Crow through HTTPS/TLS.

TLS termination and reverse proxy configuration remain a separate deployment boundary.

## Operational status and bounded logs

```bash
./deploy/status.sh
```

The status command reports the deployed Git SHA, Compose service state, health endpoint result and
persistent-directory sizes. Docker's `json-file` log driver is bounded by `CROW_PLATFORM_LOG_MAX_SIZE`
and `CROW_PLATFORM_LOG_MAX_FILES` to prevent unbounded local log growth.

Use standard Compose commands for detailed runtime logs:

```bash
docker compose logs --tail=200 crow-platform
docker compose logs -f crow-platform
```

## Consistent backup and restore

Create a backup with:

```bash
./deploy/backup.sh
```

If the service is running, the script stops it before archiving and starts it again afterward. The
archive contains independent data/config tarballs, a UTC creation time, the deployed Git SHA and
SHA-256 checksums. This deliberately favors a consistent filesystem snapshot over an online backup.

Restore only from a trusted Crow Platform backup:

```bash
./deploy/restore.sh /srv/crow-backups/platform/crow-platform-YYYYMMDDTHHMMSSZ.tar.gz
```

The restore command stops a running service, verifies all checksums before replacing either
persistent root, then starts the service and requires `/health` to recover. A failed checksum aborts
before persistent data is removed.

Backups should be copied to storage outside the Debian host as part of the site backup policy.

## Verified upgrade and code rollback path

Use the guarded upgrade script from a clean deployment checkout:

```bash
./deploy/upgrade.sh
```

The script:

1. refuses a checkout with local changes;
2. creates a cold pre-upgrade backup;
3. records the previous Git SHA and backup path under the config root;
4. runs `git pull --ff-only`;
5. rebuilds/recreates the complete manifest-driven Platform image;
6. requires the health endpoint to pass;
7. automatically resets the code to the previous SHA and rebuilds if the health gate fails.

Manual code rollback uses the recorded prior SHA, or an explicit commit SHA:

```bash
./deploy/rollback.sh
./deploy/rollback.sh <commit-sha>
```

Rollback changes the deployment checkout and container image. It does **not** automatically restore
persistent data. If a future deployment introduces a non-backward-compatible state migration, the
operator must pair code rollback with the pre-upgrade backup until a versioned migration framework
exists.

## Backup boundary

Back up both persistent roots and the generated archives. The config root contains identity records,
entitlements and audit evidence and should normally have stricter access controls than
project/runtime data.
