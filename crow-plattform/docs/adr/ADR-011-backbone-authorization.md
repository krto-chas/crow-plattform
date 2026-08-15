# ADR-011: Backbone-enforced authorization and permission-declaring manifests

## Status

Accepted as target architecture for Crow Platform 1.0. Implementation is scheduled after RC0. The current local file-based runtime does not yet provide the complete multi-tenant enforcement path.

## Context

Crow is intended to host many modules—such as Ventilation, Construction, Document Intelligence, Entity Graph, CRM, Compliance and AI assistants—for multiple organizations on shared infrastructure. Users must only access modules licensed by their organization and actions permitted by their role.

Authorization is a cross-cutting platform concern. If each module implements its own access control, every module becomes a potential bypass and behavior becomes difficult to test consistently.

Authentication—identity proofing, MFA, SSO, password policy and sessions—is outside Crow's domain and is delegated to an external OIDC identity provider.

## Problem

The platform needs one deterministic and auditable authorization model that:

- separates organization entitlements from user permissions,
- prevents cross-tenant data access,
- is mechanically verifiable through module conformance,
- applies equally to human, service and AI-driven invocations,
- preserves the modular contract model,
- defaults to denial when configuration is missing.

## Decision

Authorization is a Backbone contract and is enforced centrally before module code executes. Modules declare required permissions; they do not enforce or reinterpret them.

### 1. Backbone definition

Backbone is Crow's shared execution and governance layer. It owns public contracts, module loading, conformance, provenance, audit, persistence boundaries and platform-level security checkpoints.

### 2. Three-layer permission model

#### Entitlements

Organization-level entitlements determine which modules a tenant has licensed. Entitlements are evaluated first. A module without an entitlement is not made available for that tenant.

#### Roles and permissions

Users receive module-scoped roles such as `viewer`, `estimator`, `reviewer` or `org_admin`. Roles resolve to explicit permission strings.

A relationship-based model is deferred until cross-organization sharing becomes a real requirement.

#### Resource scope

Every tenant-bound persistent row carries `tenant_id`. The application layer applies tenant filtering to every query. In PostgreSQL deployments, row-level security provides a second line of defense.

### 3. Permission-declaring manifests

`ModuleManifest` declares every permission the module may require:

```python
ModuleManifest(
    module_id="crow.vent",
    permissions=(
        "vent.claims.read",
        "vent.claims.write",
        "vent.estimate.run",
        "vent.estimate.export",
    ),
)
```

Permission names use `<module>.<resource>.<action>`, lowercase and dot-separated.

The conformance suite verifies that:

- each referenced permission is declared,
- a module declares only permissions under its own prefix,
- the manifest schema is valid,
- the signed or tamper-evident manifest matches the loaded module.

### 4. Central enforcement

At the application edge, Crow resolves a read-only `AuthorizationContext` containing at least:

- tenant identity,
- subject identity,
- module entitlements,
- granted permissions,
- request or correlation identity.

Every module invocation passes through a single Backbone checkpoint:

1. entitlement check,
2. permission check,
3. resource-scope enforcement.

Deny by default applies. A permission not explicitly granted is denied.

### 5. AI authorization context

AI components receive the same `AuthorizationContext` as all other modules. They may not expand a user's effective permissions, infer tenant access from document content or turn a permitted read into an unapproved write or export.

AI-proposed tool calls are revalidated at the Backbone checkpoint. Authorization cannot be delegated to a model response.

### 6. Audit

Every denied authorization decision and every administrative change to roles or entitlements is recorded in the append-only audit trail with actor, tenant, permission, resource context and outcome.

Routine allows are not necessarily logged per event to avoid reducing audit utility, but deployments may enable additional logging for regulated workflows.

### 7. Identity provider

Crow consumes validated OIDC identity and access-token claims. A reference deployment may use Keycloak; enterprise installations may federate with customer identity providers. Crow does not store passwords.

### 8. Administrative surface

The administrative application is a thin UI over Backbone contracts for users, roles, entitlements and audit reading. It contains no independent authorization logic.

## Architectural rationale

Authorization is centralized because it is a platform invariant rather than domain behavior. A single enforcement point reduces duplicated logic, enables deterministic tests and fuzzing, allows conformance to detect undeclared access requirements and prevents modules from silently weakening tenant boundaries.

The design mirrors Crow's wider architecture: modules declare facts and needs; Backbone applies versioned, explainable policy.

## Consequences

### Positive

- One enforcement path to test, fuzz and audit.
- Permission declarations can be checked mechanically.
- Entitlements align security boundaries with the commercial model.
- Database row-level security limits damage from missed application filtering.
- AI and human invocations use the same authorization semantics.

### Negative

- `ModuleManifest` and the invocation path change shape.
- The central checkpoint becomes security-critical and requires extensive testing.
- Role design must remain small and understandable to avoid permission sprawl.
- Local development requires a safe development context without normalizing insecure bypasses.

## Compatibility

The change is not additive within frozen `0.5.x` contracts and therefore belongs to a later contract line. A registered migration may assign an empty `permissions` tuple to legacy manifests. Under deny-by-default, migrated but unreviewed modules expose no protected actions.

## Alternatives considered

### Module-owned authorization

Rejected because it duplicates logic and creates inconsistent security behavior.

### API-gateway-only authorization

Rejected because the gateway cannot reliably enforce domain resource scope and non-HTTP invocation paths.

### Attribute-based authorization from the start

Deferred because it increases policy complexity before a concrete requirement exists.

### Relationship-based access control

Deferred until cross-tenant project sharing or object-level collaboration is required.

## Security impact

This ADR reduces the number of enforcement points but increases the criticality of Backbone. The checkpoint, token-to-context mapping, tenant filtering, manifest validation and administrative mutation paths require dedicated threat modeling and negative tests.

## Out of scope

- per-object ACLs,
- cross-tenant sharing,
- time-of-day or network-location policy,
- identity-provider configuration,
- password storage,
- detailed secret-management strategy.

## Related documents and ADRs

- [Security Architecture](../03_Security/SECURITY_ARCHITECTURE.md)
- [Architecture](../00_Architecture/ARCHITECTURE.md)
- Crow Constitution: public contracts, provenance and reproducibility
- signed module manifests
- append-only audit trail
- future tenant-isolation and AI-authorization ADRs
