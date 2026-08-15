# Pass 94 – Vent Test Ownership

## Syfte

Slutföra repository-ägarskapet för `crow.vent` genom att flytta domänägda tester från backbone `tests/` till `modules/crow-vent-module/tests/`.

## Klassning

En importbaserad audit identifierade 13 root-tester som direkt importerade Vent-ägda paket. `test_crow_canonical.py` klassas som ett legitimt plattformsintegrationstest eftersom det verifierar backbone-canonicalisering mot Vent-adaptern och ligger därför kvar i root med explicit allowlist.

Fjorton Vent-ägda tester flyttas till modulen. Utöver tolv rena domäntester ingår `test_vent_surface.py` och `test_workbench_vent_quote.py`, som testar Vent-routes via Workbench-skalet men inte direktimporterar Vent-paket.

## Ownership-kontrakt

Manifest 1.8 sätter för `crow.vent`:

- `source_migration_complete: true`
- `test_migration_complete: true`
- `repository_ownership_complete: true`

En permanent gate verifierar att deklarerade Vent-tester finns i modulträdet, inte finns i root, och att nya root-tester inte direktimporterar Vent-ägda paket utan explicit klassning som plattformsintegration.

## Icke-mål

Ingen Vent-affärslogik eller testlogik ändras i detta pass. Flytten är ownership-/repository-städning.
