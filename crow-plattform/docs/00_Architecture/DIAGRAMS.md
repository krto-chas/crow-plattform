# Diagrams

Code-anchored Mermaid diagrams of the actual system. When code and diagram disagree, the code is right and the diagram has a defect (CAF-002 §6). Complementary flowcharts (system context, data flow) live in `SYSTEM_OVERVIEW.md`.

## 1. SDK core contracts (class model)

Source: `crow_module_sdk/models.py`, `crow_module_sdk/plugin.py`.

```mermaid
classDiagram
    class Provenance {
        +str document_id
        +str? revision
        +int? page
        +str? location
        +is_complete() bool
    }
    class Claim {
        +str id
        +str namespace
        +str subject
        +str property
        +Any value
        +str? unit
        +Decimal confidence
        +conflict_key() tuple
    }
    class ClaimSchema {
        +str namespace
        +str property
        +str value_type
        +bool unit_required
    }
    class ModuleManifest {
        +str module_id
        +str name
        +str version
        +str domain
        +str backbone_api
        +str domain_model
    }
    class ModuleCapabilities {
        +tuple claim_types
        +tuple rule_providers
        +bool technical_delta
        +bool commercial_impact
        +bool pricing_adapter
        +tuple exports
        +bool human_review_supported
    }
    class ValidationResult {
        +bool valid
        +tuple errors
        +tuple warnings
    }
    class ModuleHealth {
        +HealthStatus status
        +dict checks
        +str message
    }
    class CrowModulePlugin {
        <<protocol>>
        +manifest() ModuleManifest
        +capabilities() ModuleCapabilities
        +claim_schemas() tuple~ClaimSchema~
        +validate_claim(Claim) ValidationResult
        +healthcheck() ModuleHealth
    }
    Claim --> Provenance : provenance
    CrowModulePlugin --> ModuleManifest
    CrowModulePlugin --> ModuleCapabilities
    CrowModulePlugin --> ClaimSchema
    CrowModulePlugin --> ValidationResult
    CrowModulePlugin --> ModuleHealth
```

## 2. Decision pipeline (sequence)

Source: package chain `crow_document_intelligence` → … → `crow_estimate_revision` (see the package table in `SYSTEM_OVERVIEW.md`).

```mermaid
sequenceDiagram
    autonumber
    participant U as User / CLI
    participant DI as Document Intelligence
    participant OE as Observation Engine
    participant CE as Claim Extraction
    participant KF as Knowledge Fusion
    participant AU as Authority (Discovery + Resolution)
    participant AC as Accepted Claims
    participant DE as Decision Engine + Validation + Review
    participant TD as Technical Delta
    participant SI as Scope Impact
    participant CO as Commercial (Impact, Adjustment, Review)
    participant ES as Estimate (Line, Structure, Revision)

    U->>DI: import documents (PDF)
    DI->>DI: identity (SHA256), revision, classification, dedup
    DI->>OE: pages and regions
    OE->>CE: observations with provenance
    CE->>KF: claim candidates
    KF->>KF: cluster: SINGLETON / CONSISTENT / CONFLICTING
    KF->>AU: clusters and conflicts
    AU->>AC: resolved precedence
    AC->>DE: accepted claims
    DE->>TD: reviewed technical decision
    TD->>SI: delta vs baseline (number, text, boolean, enum)
    SI->>CO: quantity and scope changes
    CO->>ES: priced impact after commercial review
    ES-->>U: structured estimate + revision comparison (SEK)
```

## 3. Project lifecycle (state machine)

Source: `crow_module_sdk/project.py::ProjectStatus` and the transition rules in `CrowProject`.

```mermaid
stateDiagram-v2
    [*] --> draft : project_created
    draft --> ready : project_ready (policy set, claims valid)
    ready --> processing : run_started
    review_required --> processing : run_started (re-run)
    processing --> completed : run_completed (all conflicts resolved)
    processing --> review_required : run_completed (unresolved conflict)
    ready --> draft : document_revised (sources_invalidated)
    review_required --> draft : document_revised (sources_invalidated)
    completed --> draft : document_revised (sources_invalidated)
```

Notes anchored in code: a failed run does not produce a failure state — `execute_project_transactionally` rolls the aggregate back to its pre-run state and emits `run_failed` to the audit trail. `ProjectStatus.ARCHIVED` is declared but has no transition method yet; it is intentionally unreachable until an archive operation is added.

## 4. Module lifecycle (sequence)

Source: `crow_module_sdk/module_registry.py` (entry point group `crow.modules`), `crow_module_conformance` (validation, trust), ADR-006.

```mermaid
sequenceDiagram
    autonumber
    participant Dev as Module author
    participant Reg as Module Registry
    participant Conf as Conformance
    participant Trust as Trust Policy
    participant BB as Backbone

    Dev->>Reg: install wheel (entry point crow.modules)
    Reg->>Reg: discover() via importlib entry points
    Reg->>Conf: validate_plugin(plugin)
    Conf->>Conf: manifest, capabilities, schemas, healthcheck
    Conf-->>Reg: ConformanceReport (pass/fail)
    Reg->>Trust: verify signed manifest (HMAC reference; asymmetric per roadmap)
    Trust-->>Reg: trusted / untrusted
    Reg-->>BB: RegisteredModule
    BB->>BB: enforce contracts on every invocation (target: + authorization, ADR-011)
```
