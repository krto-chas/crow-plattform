# CCM Relationship Foundation — pass 8

Status: implemented and locally verified in the 0.7.0-alpha.1 baseline.

This pass adds the first deterministic relation-producing stage to the Crow Canonical Model.

## Implemented

- `CanonicalRelation` with stable canonical identity, confidence, evidence and metadata.
- `CanonicalAssembly` containing canonical objects and relations.
- `VentCanonicalAssembler` that:
  - converts known ventilation interpretations to CCM objects;
  - creates one `ventilation_system` object per explicit `system_context` and source;
  - creates evidence-backed `belongs_to` relations from interpreted objects to that system;
  - does not infer system membership when explicit context is absent.
- `CanonicalGraphBridge.persist_assembly()` which persists objects before relations.
- Regression coverage for shared system nodes and graph persistence.

## Deliberate boundary

This pass only uses explicit `system_context`. It does not infer connectivity, service areas, airflow paths or duplicate-object merges from geometry or proximity.
