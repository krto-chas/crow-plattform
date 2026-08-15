# Pass 88 — Vent Riser + Takeoff Ownership Migration

## Mål
Fortsätta Pass 87 genom att flytta nästa sammanhängande Vent-domänskiva ur backbone `src/` till `modules/crow-vent-module/`.

## Omfattning
Detta pass flyttar:

- `crow_riser_model`
- `crow_takeoff_consolidation`

Publika Python-importnamn ska vara oförändrade.

Riser och takeoff flyttas tillsammans eftersom `crow_riser_model.offer_bridge` producerar `SourceTakeoff` direkt mot `crow_takeoff_consolidation`.

## Paketeringsägarskap
Vent-modulen paketerar efter passet `py.typed` för båda paketen. Root-distributionen och root strict-mypy ska inte längre äga eller typkontrollera dessa paket som backbone-kod.

## Ownership-gate
`tests/test_vent_module_ownership.py` kräver efter passet att följande paket importeras från `modules/crow-vent-module/src/` och saknar verkliga käll-/dataartefakter under root `src/`:

- `crow_vent`
- `crow_vent_drawing`
- `crow_riser_model`
- `crow_takeoff_consolidation`

Cacheartefakter som `__pycache__` och `.pyc` räknas inte som källägarskap.

## Manifest
`modules/module_layout_manifest.json` versioneras till 1.3. Vent har därefter endast två deklarerade migrationsrester:

- `crow_vent_quote`
- `crow_benchmark_pricing`

`migration_pending_from_root_src` för `crow.vent` förblir därför `true` tills dessa är flyttade.

## Ej i detta pass
Workbench-ytor och övriga backbone-capabilities flyttas inte här. `crow_offer_export` behandlas inte som Vent-ägt i manifestet och lämnas därför orört.
