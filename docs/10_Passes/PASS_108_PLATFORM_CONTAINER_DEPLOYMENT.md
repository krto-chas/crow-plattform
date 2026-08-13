# Pass 108 — Platform reproducible Debian container deployment

## Scope

Pass 108 gives the merged Platform shell, IAM/session foundation, customer/module administration,
user lifecycle and administrative audit trail one reproducible Debian deployment contract.

## Deployment contract

- `Dockerfile` builds the Platform backbone and installs all first-party modules from the canonical
  module layout manifest.
- `compose.yaml` runs the image with health checking, explicit host bind/port configuration and
  restart supervision.
- `CROW_PLATFORM_DATA_ROOT` and `CROW_PLATFORM_CONFIG_ROOT` separate project/runtime data from
  identity, entitlement and audit configuration.
- the Debian Compose path runs `CROW_AUTH_MODE=session` and requires `CROW_SESSION_SECRET`.
- `crow-user` resolves its default configuration root from the same deployment contract, allowing
  administrator bootstrap inside the container without a special host path argument.
- `.env` is excluded from Git tracking.

## Persistent boundaries

The canonical Compose defaults are:

- `/srv/crow-data/platform` for project, upload and module runtime data;
- `/srv/crow-config/platform` for users, customer entitlements and administrative audit evidence.

The directories remain host-owned bind mounts so backup and permission policies can be managed
outside the container lifecycle.

## Future module rule

The image build calls the existing manifest-driven `crow-install-modules` command. New first-party
modules therefore become part of the Debian image when their package and canonical
`modules/module_layout_manifest.json` entry exist; no module-specific Compose or server command is
added by this pass.

## Security boundary

Host publication stays on `127.0.0.1` unless explicitly changed. Plain-HTTP internal deployment can
set `CROW_COOKIE_SECURE=false`; HTTPS deployments must set it to `true`.

This pass does not claim TLS termination, reverse proxy configuration, OIDC/SAML/MFA, secret-manager
integration, database deployment, image registry publication, cryptographically immutable audit
storage or unattended operating-system patch management.

## CI evidence

The pass is not considered verified until repository CI has passed the existing Ruff, mypy, pytest,
architecture and distribution gates plus the new Compose validation, Docker image build and
session-mode container health smoke test.
