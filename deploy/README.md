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
- config: `/srv/crow-config/platform` -> users, customer entitlements and administrative audit.

The application receives those locations through `CROW_PLATFORM_DATA_ROOT` and
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

The `crow-user` CLI now uses `CROW_PLATFORM_CONFIG_ROOT` by default, so it writes directly to the
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

TLS termination and reverse proxy configuration are not part of this deployment pass.

## Updating the server

After updating the checked-out repository, rebuild the image and recreate the service:

```bash
git pull --ff-only
docker compose up -d --build
```

Because first-party module installation is manifest-driven during the image build, this update path
also picks up newly declared modules without server-specific pip commands.

## Backup boundary

Back up both persistent roots. The config root contains identity records, entitlements and audit
evidence and should normally have stricter access controls than project/runtime data.
