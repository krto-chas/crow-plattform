# Pass 91 — Final Backbone Audit + Pressure Export Ownership

## Mål
Göra en slutlig riktad audit av root `src/` efter Vent- och Provtryckningsmigrationerna och flytta kvarvarande verksamhetsdomän som fortfarande ligger i backbone.

## Fynd
`crow_offer_export` var felklassat som backbone-capability. Paketet är Provtryckningsdomän:

- offertarbetsboken skriver uttryckligen `PROVTRYCKNING – OFFERTKALKYL`
- modellen arbetar med trapphus, schaktsträngar och provtryckningsmängder
- protokollarbetsboken importerar `PressureTestKnowledge` och `TightnessClass`
- protokollet genererar täthetsklasser, läckagefaktorer, ATC-mappning och täthetsprovningsresultat

Paketet flyttas därför oförändrat till `modules/crow-pressure-test-module/src/crow_offer_export`.

## Backbone-klassning efter audit
Följande familjer bedöms som delade plattformskapabiliteter eller värdskal och ska ligga kvar i root `src/`:

- module SDK, conformance och module host
- document/evidence/claim/knowledge/reasoning/decision pipeline
- technical review/delta och generiska commercial/estimate-lager
- import framework/orchestrator, CAD text, DWG conversion, IFC relations och building graph
- project dataset/canonical/manifest och graph/evidence rules
- regulations och entitlements
- Workbench/RC1 host samt generiska explorer/timeline-ytor

Ingen av dessa granskade familjer äger Vent-, Provtrycknings- eller OVK-specifik verksamhetslogik.

## Manifest och paketering
`modules/module_layout_manifest.json` går till version 1.6 och `crow.provtryckning` äger nu både `crow_pressure_test` och `crow_offer_export`.

Root-distributionen släpper package-data och strict-mypy-ägarskap för `crow_offer_export`. Provtryckningsmodulen paketerar `crow_offer_export/py.typed`; dess befintliga `openpyxl`-runtimeberoende täcker XLSX-exporten.

## Gate
Det befintliga layouttestet kräver nu indirekt att `crow_offer_export` finns i Provtryckningsmodulens `src/` och inte återkommer som verkligt käll-/dataartefakt under backbone `src/`.

Efter grön CI betraktas den riktade module-ownership-städningen för Vent, Provtryckning och OVK som avslutad. Nya domänmoduler måste fortsatt registreras under `modules/` enligt layoutmanifestet.
