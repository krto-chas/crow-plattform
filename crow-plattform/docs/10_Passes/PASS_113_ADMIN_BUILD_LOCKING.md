# Pass 113 — Admin surface and constrained runtime build

## Scope

Pass 113 addresses two gaps observed after the Debian deployment passes:

1. the Platform administrator APIs existed, but `/admin` did not expose the separate user-management and audit surfaces as a coherent administration entry point;
2. Pass 112 recorded the resolved Python environment after build, but normal dependency declarations still allowed direct external runtime dependencies to drift between future builds.

## Admin surface

`/admin` is the administration landing surface for a `platform-admin` identity. It exposes three explicit administration areas:

- customer and product-module access at `/admin?view=access`;
- user administration at `/admin/users`;
- administrative audit trail at `/admin/audit`.

The existing role checks remain the authorization boundary. A non-admin identity is redirected to `/app` and the admin APIs continue to enforce `platform-admin` independently of the HTML routes.

The current administrator may not deactivate their own account or remove their own `platform-admin` role through the user-management API.

## Runtime dependency boundary

`requirements/runtime-direct.lock` contains exact versions for every external runtime dependency declared by:

- Crow Platform;
- Crow Vent;
- Crow Provtryckning;
- Crow OVK.

`tests/test_runtime_dependency_lock.py` fails when a first-party production package declares an external runtime dependency that is missing from the lock or when the lock contains an unexpected/floating entry.

Pass 113 intentionally does not rewrite the existing `pyproject.toml` or root `Dockerfile` because those repository paths could not be modified safely through the connector in this pass.

Instead, the verified locked deployment path is additive:

- `deploy/Dockerfile.locked` sets `PIP_CONSTRAINT=/app/requirements/runtime-direct.lock` before installing Platform and manifest-discovered modules;
- `compose.locked.yaml` overlays the Platform build to use that Dockerfile;
- `deploy/bootstrap-locked.sh` selects the overlay for a fresh Debian bootstrap;
- `deploy/recovery-upgrade-locked.sh` selects the overlay for a recovery-guarded upgrade.

The base Python image remains digest-pinned as introduced by Pass 112. The locked image also retains `/app/crow-runtime-dependencies.txt`, generated with `pip freeze --all`, as the resolved dependency inventory.

## CI evidence requirement

Pass 113 is verified only when CI on the exact PR head demonstrates all existing quality and deployment gates plus:

1. session-mode admin login can open `/admin`, customer/module access, user administration and audit;
2. a non-admin session cannot open the admin landing page;
3. the active administrator cannot remove their own `platform-admin` role;
4. the direct-runtime lock exactly covers all declared external dependencies of current first-party production packages;
5. the locked Compose overlay parses;
6. `deploy/Dockerfile.locked` builds successfully;
7. every lock entry appears exactly in the built image's `pip freeze --all` inventory.

## Explicit boundary

This is an exact lock of the declared external runtime dependency boundary, not a full transitive wheel hash lock. Dependencies pulled transitively by FastAPI, fpdf2 and the other pinned packages are still selected by pip within the constraints published by those packages, then recorded in the image inventory.

A future supply-chain pass may generate and verify a complete transitive hash lock or immutable prebuilt application image. Pass 113 does not claim byte-for-byte PyPI graph reproducibility.
