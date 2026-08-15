# Pass 85 — Backbone src audit & module layout guard

## Syfte

Verifiera att `src/` används för backbone/delade capabilities och att verksamhetsmoduler ägs under `modules/`. Låsa regeln i ett maskinläsbart manifest och CI så att nya first-party-moduler inte kan växa in i root `src/` igen.

## Kanonisk regel

`modules/module_layout_manifest.json` är repository-layoutens sanningskälla för first-party-moduler.

- Ny verksamhetsmodul **SKALL** skapas under `modules/<modul>/`.
- First-party-modulen **SKALL** registrera sin `crow.modules` entry point i modulens egen `pyproject.toml`.
- Root `pyproject.toml` **FÅR INTE** registrera en `crow.modules` entry point.
- Root `src/` är reserverad för backbone, gemensamma capabilities och värdskal.
- Modulägd kod får inte återintroduceras i root `src/` efter att migrationen är avslutad.

## Audit av root `src/`

### Ska stanna i backbone

Följande grupper bedöms som delade plattformskapabiliteter och ska inte flyttas enbart för att Vent/OVK använder dem:

- modul-SDK/conformance,
- dokument/evidence/reasoning/decision/commercial/estimate-kedjan,
- `crow_workbench` som värdskal,
- `crow_import_framework`,
- `crow_dwg_conversion` (generell DWG→DXF/ODA-adapter),
- `crow_cad_text`, `crow_ifc_relations`, `crow_building_graph`,
- `crow_regulations`,
- `crow_entitlements`,
- projekt-, graph-, assurance- och explorer-capabilities.

### Modulägd kod som fortfarande ligger i backbone

**Provtryckning**

- `src/crow_pressure_test`
- `src/crow_workbench/pressure_test_surface.py`
- `src/crow_workbench/pressure_test_integration_surface.py`

**Vent**

- `src/crow_vent`
- `src/crow_vent_drawing`
- `src/crow_riser_model`
- `src/crow_vent_quote`
- `src/crow_benchmark_pricing`
- `src/crow_takeoff_consolidation`
- Vent-specifika Workbench-ytor (`vent_surface.py`, `vent_quote_surface.py`)

`crow_offer_export` lämnas i backbone tills vidare. Paketet används över domängränser och behandlas därför som en gemensam exportcapability tills en separat granskning visar annat.

## CI-guard

`tests/test_module_layout_manifest.py` verifierar att:

1. alla registrerade first-party-moduler finns under `modules/`,
2. alla modulrötter finns i manifestet,
3. root-projektet inte registrerar en domänmodul,
4. färdigmigrerade modulpackages inte kan dyka upp igen i `src/`,
5. kvarvarande migrationsskuld är explicit i manifestet i stället för dold.

## Nästa migrationsordning

1. Provtryckning: domänpaket + Workbench-ytor till `modules/crow-pressure-test-module`.
2. Vent core: `crow_vent` + Vent-ytor.
3. Vent takeoff/drawing/riser/quote/benchmark i sammanhängande skivor.
4. När varje skiva är flyttad sätts `migration_pending_from_root_src=false`; CI gör då återfall till root `src/` till ett hårt fel.
