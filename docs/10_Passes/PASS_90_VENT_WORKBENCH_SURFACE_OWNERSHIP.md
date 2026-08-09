# Pass 90 — Vent Workbench Surface Ownership Migration

## Mål
Slutföra Vent-modulens repository-ownership genom att flytta de två kvarvarande Vent-specifika Workbench-ytorna ur backbone `src/` och in i `modules/crow-vent-module/`.

## Omfattning
Flyttade ytor:

- `crow_workbench/vent_surface.py` → `crow_vent_module/vent_surface.py`
- `crow_workbench/vent_quote_surface.py` → `crow_vent_module/vent_quote_surface.py`

Routes och beteende ska vara oförändrade. Vent-pluginen registrerar ytorna från det egna modulträdet.

## Arkitektur
Backbone `crow_workbench` är fortsatt värdskal och gemensam plattformskapabilitet, men får inte äga Vent-domänens produktspecifika webbytor.

Efter passet äger `crow.vent` samtliga deklarerade domänpaket och produktspecifika surfaces. `migration_pending_packages` och `migration_pending_surfaces` är tomma och `migration_pending_from_root_src` sätts därför till `false`.

## Gate
`tests/test_vent_module_ownership.py` kräver att:

- samtliga sex Vent-domänpaket importeras från Vent-modulen,
- inga verkliga Vent-källartefakter finns kvar i backbone `src/`,
- `vent_surface.py` och `vent_quote_surface.py` finns i `crow_vent_module`,
- motsvarande filer inte finns under `src/crow_workbench`.

## Ej i detta pass
Ingen förändring av Vent-affärslogik, routes, entitlementregler eller UI-design görs i detta pass.
