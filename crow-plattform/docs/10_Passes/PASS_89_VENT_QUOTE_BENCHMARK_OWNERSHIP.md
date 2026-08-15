# Pass 89 — Vent Quote + Benchmark Ownership Migration

## Mål
Flytta de två sista deklarerade Vent-domänpaketen ur backbone `src/` till `modules/crow-vent-module/`.

## Omfattning
Detta pass flyttar:

- `crow_vent_quote`
- `crow_benchmark_pricing`
- installationsdata `schablon_lexikon.json`

Publika Python-importnamn ska vara oförändrade och domänlogiken ändras inte.

## Paketeringsägarskap
Vent-modulen paketerar efter passet båda paketens `py.typed` samt benchmarkmodulens `schablon_lexikon.json`. Root-distributionen och root strict-mypy äger inte längre dessa paket.

## Manifest
`modules/module_layout_manifest.json` versioneras till 1.4. Alla sex deklarerade Vent-paket är därefter migrerade till modulträdet.

`migration_pending_from_root_src` förblir dock `true` eftersom två Vent-specifika Workbench-ytor fortfarande ligger i backbone-värdskalet:

- `crow_workbench/vent_surface.py`
- `crow_workbench/vent_quote_surface.py`

Manifestet får därför ett explicit `migration_pending_surfaces`-fält så denna kvarvarande skuld är maskinläsbar och inte glöms bort.

## Ownership-gate
Regressionstesten kräver att samtliga Vent-domänpaket importeras från `modules/crow-vent-module/src/` och att verkliga käll-/dataartefakter inte återkommer under root `src/`.

## Nästa skiva
Nästa städpass flyttar de två Vent-specifika Workbench-ytorna till modulägda surfaces och kopplar värdskalet via modulens registrering. Först därefter får `crow.vent` sättas till `migration_pending_from_root_src=false`.
