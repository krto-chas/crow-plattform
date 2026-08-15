# Crow Platform 0.7.0-alpha.1 — Consolidated baseline

> **Current repository status:** This repository is the consolidated 0.7.0-alpha.1 baseline.
> The externally validated 0.5.0 Foundation remains documented below as historical evidence.
> Release-candidate status has not been declared; the criteria are defined in
> [`docs/90_Governance/RC_CRITERIA_0.7.0.md`](docs/90_Governance/RC_CRITERIA_0.7.0.md).

# Crow Backbone — 0.5.0 Foundation Release

**Crow 0.5.0 är den första fungerande och externt validerade versionen av Backbone.**

Den är inte en färdig slutanvändarapplikation. Den är en stabil, separat installerbar grund som kan ta emot domänmoduler och genomföra spårbara beslutsflöden från Claim till tekniskt och kommersiellt utfall.

## RC0 – Documentation & Architecture Freeze

Architecture Foundation documentation is available in [`docs/00_Architecture/`](docs/00_Architecture/README.md). The security target architecture and integrated Backbone authorization decision are documented under `docs/03_Security/` and `docs/adr/ADR-011-backbone-authorization.md`.


## Release-status

- Sprint A: avslutad
- Publika kontrakt: frysta för `0.5.x`
- Första externa domänmodul: validerad
- Separat wheel-installation: validerad
- CI och arkitekturgrindar: gröna
- Nästa milstolpe: Sprint B — Document Intelligence och Knowledge Fusion

## Vad som fungerar

```text
Claim
→ Conflict
→ AuthorityDecision / Human Review
→ AcceptedClaim
→ TechnicalDelta
→ CommercialImpact
→ ÄTA Opportunity
→ EstimateLine / ClientQuestion / Reservation
```

Backbone innehåller även:

- CrowProject som immutabel aggregatrot
- Decision Graph och Evidence Graph
- provenance och audit trail
- dokumentrevision och automatisk invalidation
- transaktionsgränser och rollback
- modul-SDK och plugin discovery
- konformitetskontroll och importskydd
- signerade modulmanifest som referensimplementation
- versionerade migrationer
- persistenskontrakt och JSON-referensimplementationer

## Extern validering

Crow Vent Reference Module `0.2.0` installerades som separat wheel tillsammans med Backbone och kördes i en ren miljö.

Referensfallet validerade:

```text
Ritning: 160 mm
Beskrivning: 200 mm
Bekräftad authority-regel: beskrivningen har företräde
Kommersiellt delta: 3 960 SEK
```

Modulen upptäcktes via entry point, klarade conformance-kontroll och använde inga privata Backbone-importer.

## Snabbstart

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check .
mypy
pytest
crow review --root . --release 0.5.0
```

På Windows aktiveras miljön med:

```powershell
.venv\Scripts\activate
```

## Scope

Version `0.5.0` använder strukturerad data. PDF-tolkning, OCR, bildanalys och AI-baserad Claim-extraktion ingår i Sprint B.

CDL och CKL är dokumenterade som framtida, fristående moduler och ingår inte i Backbone-runtime.

## Kompatibilitet

Den publika SDK- och conformance-ytan är fryst för `0.5.x`. Bakåtkompatibla tillägg får göras inom serien. Brytande kontraktsändringar kräver en ny minor- eller majorlinje enligt projektets versionspolicy.
\n## Sprint B1 quick start\n```bash\ncrow project create ./demo --name "Demo"\ncrow project import ./demo/crow-project.json ./underlag --recursive\ncrow project show ./demo/crow-project.json\n```\n
## Crow Platform 2.0 – Building Graph RC1, Sprint 1

Den första grafkärnan är implementerad som ett separat paket: `crow_building_graph`.
Den innehåller förstaklassobjekten `CrowObject`, `CrowRelation`, `CrowProperty`,
`CrowEvidence` och `CrowHistory`, JSON-baserad atomisk persistens, revisionshistorik,
validerade relationstyper och ett projektspecifikt REST-API i Workbench.

API:

- `GET /api/graph/relation-types`
- `GET /api/projects/{project_id}/graph`
- `POST /api/projects/{project_id}/graph/evidence`
- `POST /api/projects/{project_id}/graph/objects`
- `PATCH /api/projects/{project_id}/graph/objects/{object_id}`
- `POST /api/projects/{project_id}/graph/relations`
- `POST /api/projects/{project_id}/graph/properties`
- `GET /api/projects/{project_id}/graph/objects/{object_id}/neighbors`

## Building Graph RC1 – Sprint 2

Sprint 2 adds the first domain-neutral building structure on top of Graph Core:

- Building
- Floor
- Space
- Zone

The structure is stored as ordinary graph objects and evidence-bearing relations. No discipline-specific object is required.

### API

```text
GET  /api/projects/{project_id}/building-graph/structure
POST /api/projects/{project_id}/building-graph/buildings
POST /api/projects/{project_id}/building-graph/floors
POST /api/projects/{project_id}/building-graph/spaces
POST /api/projects/{project_id}/building-graph/zones
```


## Building Graph RC1 – Sprint 3

Sprint 3 adds a domain-neutral technical system graph. Systems are ordinary CrowObjects with discipline, system type, location, hierarchy and evidence-bearing relations.

Supported disciplines: mechanical, electrical, fire, plumbing, security, automation and generic.

### API

```text
GET  /api/system-graph/disciplines
GET  /api/projects/{project_id}/system-graph/systems
POST /api/projects/{project_id}/system-graph/systems
POST /api/projects/{project_id}/system-graph/relations
POST /api/projects/{project_id}/system-graph/service-relations
GET  /api/projects/{project_id}/system-graph/systems/{system_id}/impact
```

## Building Graph RC1 – Sprint 4: Component Graph

Sprint 4 introduces domain-neutral technical components. Components can belong to technical systems, be located in buildings/floors/spaces/zones, connect to other components and carry evidence-backed properties. This completes the RC1 graph chain from building structure through systems to components.

## Crow Platform 2.3 – Reasoning Engine RC1 Sprint 2

Sprint 2 introducerar en datadriven regelmotor ovanpå Building Graph och Traversal Engine.

- Regler definieras som JSON-data och versionssätts separat från Python-koden.
- Selektorer kan avgränsa objekt efter objekttyp, disciplin och metadata.
- Krav kan kontrollera relationer, egenskaper och evidens.
- Findings får deterministiska ID:n, severity, confidence, evidensreferenser och rekommendation.
- Standardpaketet `crow.core.quality` innehåller grundregler för systemkoppling och evidens.

API:

- `GET /api/projects/{project_id}/reasoning/rules`
- `POST /api/projects/{project_id}/reasoning/rules/validate`
- `GET /api/projects/{project_id}/reasoning/findings`
- `POST /api/projects/{project_id}/reasoning/evaluate`


## Crow Platform 2.4 – Inference Engine RC1 Sprint 2

Sprint 2 adds bounded iterative rule chaining, evidence fusion and filtered access to
derived facts and conflicts. The source graph remains immutable; inference output is
persisted separately using schema `crow-inference-v0.2`.

### Inference API

- `POST /api/projects/{project_id}/inference/run`
- `GET /api/projects/{project_id}/inference/query`
- `GET /api/projects/{project_id}/inference/conflicts`
- `GET /api/projects/{project_id}/inference/relations/{relation_id}/explanation`

## Crow Platform 2.4 – Inference Engine RC1 Sprint 3

Sprint 3 adds a persistent inference lifecycle. Every persisted run receives a stable run number,
graph and rule fingerprints, an adjacent-run diff and immutable run metadata. A changed graph is
detected as stale before inference results are consumed. Unchanged graph/rule combinations use a
deterministic cache and do not create duplicate history records.

New endpoints:

- `GET /api/projects/{project_id}/inference/status`
- `POST /api/projects/{project_id}/inference/invalidate`
- `GET /api/projects/{project_id}/inference/runs`
- `GET /api/projects/{project_id}/inference/diff`

## Crow Platform 2.4 – Inference Engine RC1 Sprint 4

Sprint 4 adds a human-controlled review boundary between derived facts and the verified Building Graph. Derived relations can be accepted or rejected, and only accepted, current inferences can be promoted to explicit graph relations. Every promotion stores the originating inference, run, rule, reviewer and note, then invalidates the current inference snapshot so it can be recalculated against the updated graph.

Review API:

- `GET /api/projects/{project_id}/inference/reviews`
- `POST /api/projects/{project_id}/inference/relations/{relation_id}/review`
- `POST /api/projects/{project_id}/inference/relations/{relation_id}/promote`

