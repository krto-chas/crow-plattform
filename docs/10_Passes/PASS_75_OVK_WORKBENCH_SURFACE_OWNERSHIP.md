# Pass 75 — OVK Workbench Surface Ownership Migration

## Scope

Flytta OVK:s Workbench-ytor ur plattformspaketet `crow_workbench` och in i `modules/crow-ovk-module` utan att ändra publika routes eller API-beteende.

## Ägarskap efter passet

OVK-modulen äger nu även sina webbytor:

- `/ovk` import/review
- `/ovk/besiktning` workflow/protokoll
- `/ovk/falt` mobil fältyta
- tillhörande `/api/ovk/...` endpoints

`crow_workbench.shell` fortsätter endast att upptäcka installerade moduler och montera deras `CrowWebModule.routers(...)`. Ingen OVK-specifik import ska finnas i Workbench/backbone.

## Kompatibilitet

Routes och payloadkontrakt ändras inte. Tester importerar routerfunktionerna från modulens ägda paket och registry-testet verifierar att Workbench fortfarande exponerar samma routes genom plugin-upptäckt.

## Gate

- Ruff
- root mypy strict
- first-party module mypy strict
- pytest
- architecture review
- distribution build

Ownership-regression ska bevisa att webbytorna laddas från `modules/crow-ovk-module` och att de gamla `src/crow_workbench/ovk_*_surface.py` inte längre finns.
