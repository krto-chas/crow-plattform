# CAF-FUT-001 Federation Roadmap

**Non-normative.** This note outlines the multi-tenant and federation direction so it exists in exactly one place. Nothing here is a requirement until it is implemented and covered by a repository ADR. The only normative source today is ADR-011 (backbone authorization, target architecture).

## Planned, in rough order

1. **Multi-tenant enforcement path (ADR-011 implementation).** External OIDC IdP (reference: Keycloak), read-only `AuthorizationContext`, entitlement + permission checks at one Backbone checkpoint, `tenant_id` on every row with Postgres row-level security as second line of defense, audit of denials and administrative changes.
2. **Distribution split.** Backbone contracts (`crow_module_sdk`, `crow_module_conformance`) as a dependency-light distribution separate from the pipeline packages and CLI, so module authors do not inherit pypdf and pipeline code.
3. **Entitlement-driven module loading.** Modules licensed per organization; unlicensed modules never load for that tenant. Entitlements shared with the commercial tier model.
4. **Third-party module trust.** Asymmetric manifest signing (e.g. Ed25519) replacing the HMAC reference implementation before external partners distribute modules (limitation noted in ADR-006).
5. **Federated deployments.** Multiple Crow installations exchanging signed, provenance-preserving artefacts (claims, estimates) across organization boundaries. Earliest after 1–4; will get its own ADRs when designed.

Superseded by this note: the archived CAS-905…CAS-943 federation documents.
