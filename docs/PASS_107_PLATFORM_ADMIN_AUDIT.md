# Pass 107 — Platform administrative audit trail

## Scope

Pass 107 adds append-only audit evidence for Platform administration.

## Audited operations

- customer creation
- customer entitlement updates
- user creation
- user updates, including active state, customer and role changes
- password replacement is represented only as `password_changed: true`

## Security boundary

Audit events never contain plaintext passwords, password hashes or password salts.

## Storage

Events are appended as JSON Lines to:

`<config_root>/audit/events.jsonl`

Each event records timestamp, actor, action, target, optional customer scope, and relevant before/after state.

## Administration surface

- `GET /api/admin/audit`
- `/admin/audit`

Both are restricted to the `platform-admin` role.

## Non-goals

This pass does not claim cryptographic tamper-evidence, external SIEM forwarding, retention policies, immutable object storage, database-backed audit indexing or compliance certification.

## CI evidence

The pass is not considered verified until the repository CI pipeline has passed Ruff format/check, mypy, strict first-party module type checking, pytest, architecture review and distribution build.
