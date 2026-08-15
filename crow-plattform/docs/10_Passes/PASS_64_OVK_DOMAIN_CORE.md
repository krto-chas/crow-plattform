# Pass 64 — OVK-domänkärna

## Syfte

Skapa en explicit OVK-domän ovanpå Crow-backbone utan att blanda ihop besiktningslogik med den befintliga `crow_ovk_pricing`-modulen eller hårdkoda branschpraxis som normkrav.

## Implementerat

- Nytt typat paket `crow_ovk` med frozen dataclasses.
- Objekt- och systemreferenser för en OVK-besiktning.
- Kontrollpunkter med explicit status: `not_checked`, `pass`, `fail`, `not_applicable`.
- Fältmätningar med Decimal, projekterat värde, uppmätt värde, enhet och transparent avvikelseprocent.
- Findings med allvarlighetsgrad, evidence origin och valfri koppling till system/kontrollpunkt.
- Åtgärder med öppen/stängd status.
- Deterministisk slutsats: `pending`, `approved` eller `deficiencies`.
- Referensvalidering för system, kontrollpunkter, findings och åtgärder.
- API-vänlig serialisering där numeriska mätvärden lämnar domänen som strängar.

## Evidensprincip

`crow_observation_engine` representerar dokumentobservationer med PDF-locator och används därför inte som en falsk modell för manuella fältmätningar. OVK-domänen bär i stället `origin` och `evidence_ref`; senare adaptrar kan länka dessa till dokumentevidens, fältfoto, instrumentmätning eller annan källa.

## Medvetna avgränsningar

- Ingen 15 %-tolerans eller annan branschschablon hårdkodas i kärnan.
- Ingen tolkning av BFS/OVK-regler görs i detta pass.
- Ingen gammal protokollimport, Workbench-vy eller protokollexport byggs i Pass 64.
- `crow_ovk_pricing` förblir separat kommersiell modul och är inte källa för besiktningsslutsats.

## Acceptance criteria

- En ej kontrollerad kontrollpunkt ger `pending`.
- En explicit underkänd kontrollpunkt ger `deficiencies`.
- En öppen obligatorisk åtgärd ger `deficiencies`.
- Fullständigt kontrollerad besiktning utan kvarstående brister ger `approved`.
- Felaktiga korsreferenser avvisas i stället för att accepteras tyst.
- Decimal används för mätvärden och serialiseras som strängar.
- Ruff, mypy strict, pytest, architecture review och distribution build ska vara gröna i CI innan merge.
