# ADR-010: Backbone-enforced authorization and permission-declaring manifests

## Status
Proposed (targets 0.6.x — additive within the frozen 0.5.x contracts is not possible; see Compatibility)

## Context
The platform vision is many modules (Vent, VS, El, Document Intelligence, Entity Graph, CRM, Compliance, AI Assistant) served to many organizations from shared infrastructure. Users must only reach the modules their organization is entitled to and the actions their role permits. Authorization is a cross-cutting concern like auditing (ADR-004): if each module implements its own access control, every module becomes a potential hole. Authentication (identity, MFA, SSO, sessions) is explicitly out of scope for Crow and delegated to an external OIDC identity provider.

## Decision
Authorization is a Backbone contract, enforced centrally before any module code runs. Modules declare, never enforce.

### 1. Three-layer permission model
- **Entitlements (organization level).** Which modules an organization has licensed. Evaluated first; an unlicensed module is never loaded for that tenant. Entitlements are the same data that drives the pricing tiers.
- **Roles (user level, per module).** Role-based access control with a small fixed vocabulary per module (e.g. `viewer`, `estimator`, `reviewer`, `org_admin`). Roles map to sets of permission strings. No relationship-based model (ReBAC) until cross-organization project sharing exists.
- **Resource scope (row level).** Every persisted row carries `tenant_id`. The application layer filters by tenant on every query, and PostgreSQL row-level security policies act as the second line of defense so a missed application check cannot leak data across tenants.

### 2. Permission-declaring manifests
`ModuleManifest` is extended with a declaration of every permission the module can require:

```python
ModuleManifest(
    module_id="crow.vent",
    ...,
    permissions=(
        "vent.claims.read",
        "vent.claims.write",
        "vent.estimate.run",
        "vent.estimate.export",
    ),
)
```

Naming convention: `<module>.<resource>.<action>`, lowercase, dot-separated. The conformance suite gains a check: a module must declare every permission it references, and may not declare permissions outside its own module prefix. Because manifests are signed (ADR-006), the permission declaration is tamper-evident.

### 3. Central enforcement
- The Backbone resolves an `AuthorizationContext` (tenant, user, entitlements, granted permissions) from validated IdP token claims at the edge, once per request.
- Every module invocation passes through a single Backbone checkpoint: entitlement check, then permission check, then resource-scope filter. Modules receive the context read-only and must not re-derive or bypass it.
- Deny by default. A permission not explicitly granted is denied.

### 4. Audit
Every authorization decision that denies access, and every administrative change (role grant, entitlement change), is recorded in the same append-only audit trail as project events, with actor, tenant, permission, and outcome. Routine allows are not logged per event to keep the trail useful.

### 5. Identity provider
Authentication is externalized to an OIDC IdP (reference deployment: Keycloak; enterprise SSO via the customer's IdP). Crow consumes ID/access tokens and maps token claims to the `AuthorizationContext`. Crow never stores passwords.

### 6. Admin surface
The admin module is a thin UI over these contracts: user and role management, entitlement management per organization, and an audit-log reader. It holds no authorization logic of its own.

## Consequences
- One enforcement point to test, fuzz, and audit instead of eight.
- Conformance can verify permission declarations mechanically, so a module cannot silently widen its access.
- Entitlements double as license enforcement, aligning security with the commercial model.
- Tenant isolation survives application bugs via row-level security.
- Cost: `ModuleManifest` and the plugin invocation path change shape, which is a breaking contract change and therefore requires the 0.6 version line per the 0.5.x freeze. A migration is registered (ADR-007) so 0.5.x manifests upgrade by receiving an empty `permissions` tuple, which under deny-by-default means an unmigrated module exposes nothing.

## Out of scope
- Fine-grained per-object ACLs and cross-tenant sharing (revisit with ReBAC if project sharing between organizations becomes a requirement).
- Attribute-based rules (time-of-day, IP restrictions).
- The IdP's own configuration (MFA policy, password policy) — owned by deployment, not by Crow.
