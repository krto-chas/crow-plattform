# Pass 65 — OVK-import

## Syfte

Koppla dokumentevidens från `crow_observation_engine` till OVK-domänen utan att gissa normativa slutsatser eller betydelsen av otydliga tabellvärden.

## Implementerat

- Nytt typat paket `crow_ovk_import`.
- Import från `ObservationCollection` med bibehållen PDF-locator som `evidence_ref`.
- Explicit systemigenkänning för vanliga ventilationsbeteckningar.
- Luftflödesmätning importeras endast när texten uttryckligen märker ett värde som uppmätt/mätvärde.
- Projekterat värde kopplas endast när det uttryckligen märks och har samma enhet.
- Mätpunkter som B1/L1/K1/C1/D1 kan kopplas till mätningen när de står i samma evidensrad.
- Rader märkta `Anmärkning` eller `Brist` importeras som STATED findings med neutral INFO-severity och utan automatiskt åtgärdskrav.
- Observationer som inte säkert kan mappas sparas i `unmapped` för review i stället för att tappas eller tolkas kreativt.

## Evidensprincip

Importen skapar inte PASS/FAIL och tolkar inga BFS-regler. Otydliga rader som `B1 FTX01 34 l/s 40 l/s` får inte antas betyda uppmätt respektive projekterat värde. De explicita systemuppgifterna kan återanvändas, men de oetiketterade talen blir inte mätningar.

## Medvetna avgränsningar

- Ingen direkt PDF-läsare byggs här; plattformens befintliga document/observation-pipeline är indatakälla.
- Ingen OCR.
- Ingen normtolkning eller 15 %-regel.
- Ingen Workbench-vy eller persistens ännu.
- Ingen automatisk severity-klassning av gamla anmärkningar.

## Acceptance criteria

- Explicit `uppmätt` luftflöde blir en STATED `OvkMeasurement` med evidence-ref.
- Explicit projekterat värde importeras bara med kompatibel enhet.
- Oetiketterade numeriska tabellvärden gissas inte.
- Explicit anmärkning/brist behåller sin källtext utan uppfunnen severity eller åtgärdsplikt.
- Omatchad evidens finns kvar för review.
- Ruff, mypy strict, pytest, architecture review och distribution build ska vara gröna före merge.
