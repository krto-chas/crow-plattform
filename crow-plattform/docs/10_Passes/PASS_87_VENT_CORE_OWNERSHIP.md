# Pass 87 — Vent Core Ownership Migration

## Mål
Flytta Vent-kärnan ur backbone `src/` till den first-party-modul som redan representerar domänen: `modules/crow-vent-module/`.

## Omfattning
Detta pass flyttar endast:

- `crow_vent`
- `crow_vent_drawing`
- Vent-lexikonet `vent_beteckningar_lexikon.json`

Publika Python-importnamn ska vara oförändrade.

## Medvetet kvar till senare pass
Vent-migrationen är fortfarande pågående efter detta pass. Följande domänpaket/ytor flyttas i separata skivor:

- `crow_riser_model`
- `crow_takeoff_consolidation`
- `crow_vent_quote`
- `crow_benchmark_pricing`
- Vent-specifika Workbench-ytor

Generella backbone-capabilities såsom CAD/DWG/import, Building Graph och evidensmotor stannar i root `src/`.

## Ownership-gate
Regressionstest kräver att `crow_vent` och `crow_vent_drawing` importeras från `modules/crow-vent-module/src/` och att inga root-kopior finns kvar under `src/`.

`modules/module_layout_manifest.json` fortsätter därför ha `migration_pending_from_root_src=true` för `crow.vent` tills samtliga deklarerade Vent-paket har flyttats.
