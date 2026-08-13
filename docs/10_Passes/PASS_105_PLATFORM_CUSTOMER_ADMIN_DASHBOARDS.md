# Pass 105 — Platform customer/admin dashboards

## Scope

Pass 105 turns the Pass 103/104 shell and IAM foundation into explicit customer and administrator surfaces without coupling Platform to any individual domain module.

## Included

- `/` routes authenticated users to `/app` or `/admin` based on role.
- `/app` requires an authenticated customer context in session mode.
- `/admin` requires `platform-admin`; non-admin users are routed back to `/app`.
- Customer dashboard renders the shared Workbench plus only the product modules returned by `/api/me/modules`.
- Admin dashboard separates customer entitlements, product catalog state and runtime module discovery.
- Admin can bootstrap a new customer with an empty entitlement document through `POST /api/admin/customers`.
- Admin can continue to activate/deactivate product modules and validity dates per customer.
- Session metadata now exposes the configured auth mode so the UI can show logout only for session authentication.
- The UI remains registry/catalog driven: future modules appear through the product/runtime catalogs rather than hard-coded dashboard branches.

## Deliberate boundaries

This pass does not add enterprise identity providers, MFA, password lifecycle, user administration, billing/subscriptions, audit logging or a replacement for the existing Workbench project surface.

## Evidence gate

The pass remains unverified until repository CI has passed Ruff format/check, mypy, strict first-party module type checking, pytest, architecture review and distribution build.
