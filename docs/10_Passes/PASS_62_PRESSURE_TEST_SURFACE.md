# Pass 62 — Provtryckning: produktvy och mätbedömning

## Syfte

Göra den befintliga `crow_pressure_test`-kunskapen användbar i Workbench utan terminal.
Passet bygger ingen ny normkälla: läckagefaktor, ATC-klass och standardregister läses från
befintligt `tathetsprovning_lexikon.json` via `PressureTestKnowledge`.

## Byggt

- `crow_pressure_test.workflow` med frozen dataclasses för produktens mätbedömning.
- Tillåtet läckage beräknas av befintlig `PressureTestKnowledge.allowed_leakage_flow`.
- Uppmätt läckage ger deterministiskt `pass`, `fail` eller `not_measured`.
- Mått och beräknade flöden serialiseras som strängar i API-payloaden.
- Proveniens visas separat för täthetsklass, provtryck och valfria INFERRED-antaganden.
- En INFERRED-post måste vara uttryckligen bekräftad innan resultatet blir
  `ready_for_protocol=true`.
- `POST /api/provtryckning/projects/{project_id}/evaluate` ligger under modulens
  entitlement-prefix.
- `/provtryckning` ger projektval, krav/proveniens, kanalarea, mätvärde och PASS/FAIL.
- Test låser att Provtryckning kan vara licensierad utan kommersiell Vent-entitlement;
  den tekniska relationen är `data_dependencies=["vent_model"]`, inte ett köpkrav.

## Avgränsning

Pass 62 genererar inte XLSX/PDF-protokoll från Workbench och persisterar inte mätserier.
Pass 54:s XLSX-protokolladapter finns kvar som presentationsadapter och kopplas in i ett
senare vertikalt pass. Automatisk hämtning av kanalarea/system från `vent_model` är också
ett separat integrationssteg.

## Acceptance criteria

- Modul-API utan Provtryckning-entitlement ger 403.
- Provtryckning-entitlement utan Vent-entitlement kan köra bedömningen.
- Mätvärde inom tillåtet läckage ger `pass`; över gränsen ger `fail`.
- INFERRED utan bekräftelse blockerar protokollstatus även om mätningen är godkänd.
- Ruff, mypy strict, pytest, architecture review och distribution build ska vara gröna i CI.
