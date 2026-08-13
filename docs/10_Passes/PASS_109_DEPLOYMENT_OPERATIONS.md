# Pass 109 - Deployment operations

## Scope

Pass 109 hardens the Debian deployment introduced in Pass 108 with operational controls that can be
verified without claiming a production environment that has not been observed.

## Added deployment controls

- cold backup of both persistent roots;
- SHA-256 integrity manifest plus deployed Git SHA in every backup;
- restore verification before destructive replacement;
- health/status command for the deployed service;
- bounded Docker `json-file` logging;
- clean-tree guarded upgrade workflow with a mandatory pre-upgrade backup;
- automatic code rollback when the post-upgrade health gate fails;
- explicit manual rollback to the previously recorded or supplied Git commit.

## Evidence boundary

CI validates shell syntax and performs a real backup/restore round-trip against temporary data and
configuration roots. The existing container smoke test continues to validate Compose configuration,
image construction, session-mode startup and `/health`.

CI does not prove behavior on the user's Debian host, external backup storage, TLS termination,
network routing or unattended recovery after host failure. Those require environment-specific
verification.

## State migration boundary

Code rollback intentionally does not rewrite persistent state automatically. A future
non-backward-compatible persistence change requires a versioned migration/rollback contract. Until
then, the pre-upgrade archive is the recovery boundary for persistent data.

## Non-goals

- reverse proxy or TLS certificate lifecycle;
- OIDC/SAML/MFA;
- remote log aggregation;
- external immutable audit storage;
- database migration orchestration;
- host OS patch orchestration.
