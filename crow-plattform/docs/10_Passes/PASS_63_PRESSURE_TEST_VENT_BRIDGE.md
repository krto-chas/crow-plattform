# Pass 63 — Provtryckning: Vent-brygga och protokollexport

## Syfte

Koppla provtryckningens produktflöde närmare den evidensbärande ventilationsmodellen och göra ett faktiskt XLSX-protokoll tillgängligt via Workbench/API utan att skapa en ny norm- eller beräkningskälla.

## Byggt

- `crow_pressure_test.vent_bridge` översätter `crow_riser_model.RiserString` till provkandidater.
- För cirkulära kanaler härleds mantelyta deterministiskt från dimension och längd; ursprunglig `evidence` följer kandidaten.
- `POST /api/provtryckning/projects/{project_id}/vent-candidates` tar riser/vent-strängar och returnerar provkandidater samt explicit `skipped` för ej tolkbara strängar.
- `POST /api/provtryckning/projects/{project_id}/protocol.xlsx` återanvänder Pass 62:s evaluate-endpoint och exporterar endast det redan bedömda resultatet.
- XLSX-adaptern räknar inte om q_max; resultat, mått, proveniens och standardreferenser kommer från evaluate-payloaden.
- Protokollexport blockeras med 409 om resultatet inte är `ready_for_protocol`, exempelvis när ett INFERRED-antagande är obekräftat.

## Viktig avgränsning

Workbench persisterar ännu inte en kanonisk `vent_model` per projekt som Provtryckning kan hämta automatiskt. Passet bygger därför den typade och testade bryggan från befintliga `RiserString`-objekt till provkandidater, men påstår inte att automatisk projektuppladdning redan finns. När `vent_model`-persistens exponeras kan endpointen matas direkt från den källan utan att ändra provtryckningens area- eller evidenskontrakt.

Rektangulära kanaler stöds inte av denna första brygga; okänd dimension flaggas i `skipped` och får inte tyst approximeras.

## Acceptance criteria

- Ø160 × 10 m ger deterministiskt 5.026548 m² mantelyta.
- Kandidaten behåller riser-modellens evidence.
- Ogiltiga/ej stödda dimensioner hamnar i `skipped`, inte i beräknade kandidater.
- Protokoll-XLSX innehåller exakt utvärderad klass, tryck, area, q_max, mätvärde, resultat och proveniens.
- Obekräftad INFERRED-proveniens blockerar protokollexport.
- Ruff, mypy strict, pytest, architecture review och distribution build ska vara gröna före merge.
