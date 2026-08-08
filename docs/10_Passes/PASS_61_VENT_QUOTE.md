# Pass 61 — Vent-offert ovanpå kalkyl

## Syfte
Stäng Vent-flödet från mängd/kalkyl till ett användbart offertutkast utan att skapa en ny prissanningskälla. Offerten konsumerar resultatet från `crow_takeoff_consolidation.pricing` och lägger endast explicita kommersiella påslag ovanpå kalkylens självkostnad.

## Implementerat
- Nytt typat paket `crow_vent_quote` med frozen dataclasses.
- `build_vent_quote()` validerar `crow-takeoff-pricing`-payload och bygger offert med Decimal.
- Omkostnad, risk och vinst anges explicit i procent; inget dolt standardpåslag finns.
- Alla belopp serialiseras som strängar i API-payloaden.
- Offerten markeras `ready_to_send=false` om kalkylen har oprissatta poster eller reservationer.
- Ny entitlement-skyddad endpoint `POST /api/vent/projects/{project_id}/quote` återanvänder befintlig Vent-takeoff och prissättning.
- Ny vy `/vent/offert` med projekt, kalkylindata, kommersiella påslag, omfattning, undantag, offertsummering, CSV-export och webbläsarens utskrift/PDF.

## Avgränsningar
- Ingen servergenererad PDF i detta pass; utskrift/PDF använder webbläsarens printfunktion.
- Ingen lagring eller revisionshantering av offert ännu.
- Ingen automatisk rekommenderad marginal eller branschschablon. Kommersiella påslag är användarens uttryckliga indata.
- Pass 54:s offert/protokollexport för provtryckning återanvänds inte eftersom det är en annan domän.

## Acceptance criteria
- Vent-entitlement krävs för offert-API.
- Samma takeoff/prisbok ger deterministisk självkostnad och offert.
- Decimal används i offertdomänen och belopp lämnar API som strängar.
- Oprissatta/reserverade poster kan inte ge en sändklar offert.
- Ruff, mypy strict, pytest, architecture review och distribution build ska vara gröna i CI innan merge.
