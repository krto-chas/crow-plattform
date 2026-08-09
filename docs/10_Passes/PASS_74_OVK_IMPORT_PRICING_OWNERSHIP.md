# Pass 74 — OVK Import + Pricing Ownership Migration

## Scope

Flytta `crow_ovk_import` och `crow_ovk_pricing` från backbone `src/` till `modules/crow-ovk-module` utan att ändra publika importnamn eller domänbeteende.

## Ägarskap efter passet

OVK-modulen äger nu:

- `crow_ovk`
- `crow_ovk_field`
- `crow_ovk_workflow`
- `crow_ovk_import`
- `crow_ovk_pricing`

`crow_regulations` ligger kvar i plattformen som gemensam capability. Workbench-ytor ligger kvar som integrationslager tills separat migrationspass.

## Gate

- Ruff
- root mypy strict
- first-party module mypy strict
- pytest
- architecture review
- distribution build

Ownership-regressioner ska bevisa att de fem OVK-paketen laddas från modulträdet och att import- samt prissättningsbeteendet fortfarande fungerar.
