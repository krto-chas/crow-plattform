# ADR-012: The building graph is the shared building model; modules add domain knowledge

## Status

Proposed. Becomes Accepted when merged. Implementation is staged (see Migration) and must not change the OVK 1.0 release gates.

## Context

Crow's intent is that Core provides the foundation and modules provide domain expertise. For decisions and provenance this holds: modules implement the Module SDK contract (manifest, capabilities, claim schemas, validation, health).

For the *building itself* it does not hold. A review of `main` (November 2026) found the same building described in five places with no shared identifiers:

| Where | What it holds | Persisted |
|---|---|---|
| `crow_building_graph` (Core) | building, floor, space, zone, technical systems and components, relations, properties with unit, evidence, revision and history | per project, `building-graph/graph.json` |
| `crow_ovk_fastighet` + structure registry (OVK module) | buildings, units, rooms, persistent measurement points, technical spaces, systems | per project, module-owned JSON |
| `crow_vent_drawing` (Vent module) | apartments with stairwell, floor, rooms and area; floor elevations | not persisted |
| `crow_riser_model` (Vent module) | vertical duct strings per apartment and air type, with dimension and computed length | not persisted |
| `crow_pressure_test` (Pressure-test module) | test candidates with duct surface area, derived from riser strings | not persisted |

No module reads or writes the building graph. The reasons are structural, not accidental:

- The web extension contract is `routers(data_root: Path)`. A module receives a directory and nothing else, so each module invents its own files.
- The graph service is constructed inside the Workbench application factory. It is not part of the Module SDK and cannot be obtained by a module without knowing a private path.
- `MODULE_CONTRACT.md`, `MODULE_DEVELOPMENT_GUIDE.md`, `PERSISTENCE_CONTRACT.md` and the constitution do not mention the building graph.
- `CanonicalGraphBridge` can persist canonical objects into the graph, but it is only reachable from one manual Workbench endpoint.

The trigger for deciding this now is OVK 2.0 (`OVK_PRODUCT_VISION_2_0.md`): floors, shafts, separate ducts, terminal connections and the CAD Light schematic editor. The same topology is wanted by balancing (injustering), estimating and pressure testing. Built inside one module it would become a sixth description of the same building.

## Problem

We need one building model that

- every module can read and extend through a public contract,
- keeps technical topology separate from graphical placement,
- distinguishes proposals from verified observations,
- is safe for an editor that makes many small concurrent changes,
- can be adopted step by step without rewriting working modules or delaying OVK 1.0.

## Decision

### 1. Principle

Core owns what the building *is*. Modules own what is *known and done* about it.

Building, floor, stairwell, shaft, space (apartment, premises, room), zone, technical system, technical component and the connections between them live in the building graph. Modules store their own domain records — inspections, findings, measurements, prices, test results, drawings — and refer to graph objects by ID. A module must not persist its own copy of building structure.

### 2. Modules receive a context, not a path

The Module SDK gains a `ModuleContext` that replaces the bare `data_root`:

- `context.graph(project_id)` — the project's building graph service,
- `context.storage(project_id)` — a module-private, namespaced storage root for domain records,
- room for tenant and authorization scope when ADR-011 is implemented.

`routers(data_root)` remains supported during the transition. A module opts in by implementing the context-based variant; the shell prefers it when present. This keeps ADR-003 intact: the graph becomes reachable through the SDK instead of through private Core imports.

### 3. Core stays domain-neutral; ventilation terms come from a vocabulary module

Core adds only neutral structural types that are missing today: `stairwell` and `shaft`, plus floor elevation as a property of `floor`.

Ventilation-specific types — air terminal, duct (airway), collecting duct, fan, air handling unit — are not Core types. They are `component_type` values defined by a shared first-party vocabulary module (`crow.ventilation`, no user interface, not licensed separately). OVK, Vent and Pressure-test declare it in `requires_modules`. It owns the vocabulary, validation rules for a duct network (supply and extract not mixed, every terminal connected or explicitly unconnected, no cycles where the system type forbids them) and shared derivations such as riser length from floor elevations.

### 4. Three kinds of information are kept apart

- **Topology** — objects and relations in the graph. This is the technical truth.
- **Layout** — position, size and layer of a symbol in a schematic. Stored by the CAD Light module, keyed by graph ID. Moving a symbol never changes a relation.
- **Quantities** — dimension, length, area, flow. Stored as graph properties with unit and source. A quantity is entered, imported or derived by a stated rule. It is never measured from a schematic, because the schematic is not to scale.

### 5. Verification status is explicit

Every object, relation and property carries a verification status separate from confidence:

- `proposed` — produced by a template, an import or an inference,
- `stated` — taken from a project document,
- `verified` — confirmed on site or by a qualified reviewer, with who and when.

Templates and drawing interpretation only ever produce `proposed`. Only `verified` content may be presented as fact in a certificate, protocol or operating card.

### 6. Storage: PostgreSQL through SQLAlchemy

The current repository reads and rewrites the whole graph file for each operation and has no locking. Before any module depends on it, the graph store must provide:

- atomic batch writes (one editor action = one transaction),
- an expected-revision check so concurrent edits fail instead of overwriting,
- acceptable performance at a realistic size (target: a property with 500 units and their rooms, terminals and ducts).

The building graph is therefore the first part of Crow to move from JSON files to a database:

- **PostgreSQL** is the production store, accessed through **SQLAlchemy 2.0**, with schema changes managed by **Alembic** under the existing migration policy (ADR-007).
- The graph keeps a repository contract, as `PERSISTENCE_CONTRACT.md` requires. Core and modules depend on the contract, not on SQL.
- **SQLite** through the same SQLAlchemy code is supported for local single-user mode. The schema uses portable column types only; PostgreSQL-specific types are not used in the graph tables.
- CI runs the graph store tests against a real PostgreSQL service, not only SQLite, so that the two cannot drift apart unnoticed.
- Every row carries `tenant_id` from the first migration, so that ADR-011 can be enforced later without a schema rewrite.
- Existing `building-graph/graph.json` files are imported once by a migration and kept as read-only backups.

Scope of this decision: the building graph only. Other JSON-backed stores move when they are next reworked, one at a time. The OVK field application's files and SQLite stores for offline sync and issuance locks are explicitly left as they are until OVK 1.0 has shipped.

### 7. Conformance

The architecture review gains a rule that flags a module persisting building structure of its own. Existing cases (the OVK structure registry and the riser-model input) are listed as known exceptions with an owner and are removed as they migrate.

## Migration

Each step is a small, separately mergeable change.

1. `ModuleContext` in the SDK and shell; graph service obtainable through it. No behaviour change.
2. Graph store on PostgreSQL through SQLAlchemy and Alembic: batch writes, revision check, size test, import of existing graph files, PostgreSQL in CI and in the Compose stack, database included in backup and restore.
3. Core: `stairwell`, `shaft`, floor elevation, verification status.
4. `crow.ventilation` vocabulary module with network validation.
5. OVK structure registry mirrored into the graph through an adapter. The registry remains the source of truth until OVK 1.0 has shipped; only then is ownership switched.
6. Riser model and pressure-test candidates read from the graph instead of ad hoc input.
7. CAD Light: generated read-only schematic from the graph.
8. CAD Light: desktop editor (layout first, connections second).

Steps 1–4 do not touch OVK field data or release gates.

## Consequences

### Positive

- One set of identifiers for a building across inspection, estimating, balancing and pressure testing.
- CAD Light becomes a view and editor of shared data, usable by every ventilation module.
- Provenance, revision and history come from Core instead of being rebuilt per module.
- The context object is the natural seam for tenant isolation (ADR-011).

### Negative

- Modules lose the freedom to shape building data for their own convenience.
- The graph store must be rebuilt before it is useful, which is work with no visible feature.
- PostgreSQL becomes a required service in production. Deployment, backup and restore must cover it, and the backup/restore acceptance for OVK 1.0 has to be re-run once the database is part of the stack.
- During migration the OVK registry and the graph coexist and must be kept consistent by the adapter.

## Alternatives considered

### Topology inside the OVK module

Fastest for OVK 2.0, but forces other modules to depend on OVK or to duplicate the model.

### A new shared topology module with its own storage

Avoids touching Core, but duplicates what `crow_building_graph` already provides and leaves the graph unused.

### Harden the JSON file store instead of introducing a database

Locking and batch writes can be added to files, but tenant isolation, concurrent editing and queries across a large graph would each have to be built by hand. PostgreSQL is already the stated target in ADR-011.

### Rewrite the platform in TypeScript to match SecAssess

SecAssess benefits from PostgreSQL and an ORM, not from its language. The same is available in Python, where document, drawing and calculation libraries are stronger and the existing typed and tested code base is kept.

### Keep per-module models and synchronise them

Every pair of modules needs a mapping, and there is still no single identity for a shaft or a terminal.

## Out of scope

- Choice of front-end technology for the CAD Light editor.
- A mobile or offline editor. The first editor is desktop only; the field app may get a read-only view.
- System flow diagrams, control diagrams and operating cards (later steps of the OVK 2.0 vision).
- Enforcement of tenant isolation (ADR-011).

## Open questions

- How a platform project maps to a property with several buildings, and whether existing OVK `unit_id` and `point_id` values are reused as graph IDs.
- How the offline field app's sync revisions relate to graph revisions once ownership is switched in step 5.
- Whether drawing import (`crow_geometry_framework` topology) should write `proposed` relations directly or go through review first.

## Related documents and ADRs

- ADR-003 Stable module boundary
- ADR-004 Project aggregate
- ADR-007 Versioned migrations
- ADR-009 Crow Knowledge Language
- ADR-011 Backbone-enforced authorization
- `docs/OVK_PRODUCT_VISION_2_0.md`
- `docs/MODULE_CONTRACT.md`, `docs/PERSISTENCE_CONTRACT.md`
