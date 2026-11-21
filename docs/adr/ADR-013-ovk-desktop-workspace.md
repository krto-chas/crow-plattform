# ADR-013: OVK Desktop 1.0 – terminology, roles, shared inspections and issuing

## Status

Proposed. Becomes Accepted when merged. Decided by the product owner on 2026-11-21 in response to the inventory of `main` @ `330f0d4`. The workflow and contracts are described in [OVK Desktop 1.0](../design/OVK_DESKTOP_1_0.md).

## Context

The OVK desktop workspace is to cover the whole chain from customer and property to an issued and delivered protocol, for a single inspector as well as for organizations with several users. The inventory found that most domain functions exist as separate pages, but that five questions had no decided answer:

- "Customer" means two different things in the code and in the product requirements.
- Roles exist in Core sessions, but only two OVK routes check them, and they do so inside the module.
- An inspection has exactly one inspector and is synchronized as one whole snapshot.
- Nothing ties the person who issues a certificate to the inspector of the assignment.
- Tenant isolation is missing, and it was unclear whether it belongs to Desktop 1.0.

## Decision

### 1. Terminology: organization and customer

- **Organization** is the company that uses Crow: the inspection firm. In code this is the existing `CustomerContext.customer_id`. The identifier keeps its name; renaming a Core contract is not justified by a wording change.
- **Customer** (kund) is the party the inspection is carried out for: the property owner or the party ordering the work. This is an OVK domain record owned by the OVK module.

User interface texts, documentation and new OVK code use these two words in this sense. New OVK code must not use `customer` for the ordering party in identifiers; use `kund`.

### 2. Roles are declared by the module and checked through Core

The OVK module owns its roles: administrator, work leader (arbetsledare), inspector (besiktningsman) and protocol reviewer (protokollgranskare). A user may hold several.

- The module declares its roles and which actions each role permits.
- The check is performed in the backend by one shared dependency that reads the Core session. A route never inspects `roles` on its own.
- Core gains no knowledge of OVK roles. The dependency takes the required action as an argument; the mapping from role to action is module data.
- The user interface hides what a user may not do, but hiding is never the control.
- An organization with a single user needs no role administration: when an organization has exactly one active user, that user holds all OVK roles.

This is a step towards ADR-011, not an implementation of it. The two existing in-module checks (`ovk_correction_reviewer`, `ovk_correction_issuer`) move to the shared dependency when their routes are next changed.

### 3. Tenant isolation follows the roadmap

Tenant isolation is not part of Desktop 1.0. It remains in roadmap block R8 and must be in place before any external organization is onboarded. Until then the platform runs for one organization.

To keep R8 additive, every new desktop route resolves its data through one module-internal scope function that takes the Core session. Today it returns all projects; in R8 it filters by organization. No new route may list or open projects by any other path.

PostgreSQL for OVK data also waits, as ADR-012 already states.

### 4. A shared inspection is one inspection with one protocol

When several inspectors work on the same property, they work in the same inspection. The result is one protocol and one certificate.

- Work is assigned in parts: a part is a set of units (apartments, premises) or technical spaces of the inspection. The whole inspection may be one part.
- Each inspector synchronizes only the parts assigned to them. The server keeps one revision per part and composes the inspection from the parts.
- A synchronization of one part can therefore not overwrite another inspector's work. A conflict within a part is reported as today, never resolved silently.
- Reassignment creates a new assignment record. Earlier assignments and what was synchronized under them are kept.
- An inspection with a single part behaves exactly as today. The existing whole-snapshot contract remains valid for it.

This changes the synchronization contract and is therefore built only after the single-inspector pilot works. The contract is specified before any code is written, and the field application is changed only as far as the contract requires.

### 5. The inspector signs and sends

The certificate and protocol are always signed and sent by the inspector who carried out the inspection. A reviewer approves the material for issuing but never issues.

- A registered inspector is linked to a user account.
- Issuing is permitted only for the user linked to an inspector of the inspection, holding a certification valid on the inspection date.
- For a shared inspection one inspector is named responsible and signs. The others are listed as participating.
- Review and issuing are separate records with who and when, as today. For a single inspector the same person may do both; the two steps remain.

## Consequences

### Positive

- One word for each of the two meanings of customer.
- One place to change when ADR-011 and R8 are implemented.
- The single-inspector flow is unchanged by the decisions on sharing and roles.
- The signature on an issued document can be tied to a certified person.

### Negative

- The platform remains single-organization until R8. Desktop routes written before then are not safe for several organizations, and must not be exposed to one.
- The inspector register and user accounts must be linked before issuing can be restricted.
- Per-part synchronization adds a second synchronization path that must be tested against the first.

## Alternatives considered

- **Tenant isolation now.** Deferred by the product owner; the roadmap order stands.
- **One inspection per inspector, merged in the office.** Rejected: it creates several server identities for the same inspection and a manual merge step.
- **Reviewer may issue.** Rejected: the certified inspector is responsible for the assessment.
- **Role checks in each route.** Rejected: it repeats what ADR-011 identifies as the main risk.

## Related

- [ADR-003](ADR-003-module-boundary.md), [ADR-011](ADR-011-backbone-authorization.md), [ADR-012](ADR-012-building-graph-as-shared-model.md)
- [OVK roadmap](../OVK_PRODUCT_ROADMAP_1_0.md), [Property-first](../design/OVK_PROPERTY_FIRST.md)
