# Pass 52 — Risermodell och offertbrygga

## Syfte
Generalisera schaktmodellen från Berghällen-anbudet till en återanvändbar
kvantitetskedja: lägenhetsdata + plushöjder + systemkonfiguration → vertikala
strängar → material- och offertmängder. Berghällen är referensvalidering,
inte specialfall — samma modell ska bära nästa förfrågningsunderlag.

## Byggt — nytt paket `crow_riser_model`
- `models.py` — `RiserConfiguration` (top_plan per betjäningsområde,
  string_kinds ur flödesschemat, vindstillägg, dimension/mediumkod per kind),
  `LevelTable` (plushöjder → höjdskillnad), `ApartmentLike` som Protocol så
  vilken extraktionskälla som helst duger (crow_vent_drawing, DWG, manuell).
- `build.py` — `build_riser_model`: strängar per lägenhet med Decimal-längd;
  lägenheter utan plushöjd hamnar i `skipped` med orsak, aldrig tyst borta.
- `offer_bridge.py` — två utgångar:
  `to_source_takeoff` (materialsida: kanalrader per medium/dimension in i
  befintlig takeoff-konsolidering med (kind, code, dimension)-nyckeln) och
  `pressure_test_service_quantities` (offertsida: strängar att prova per
  trapphus, delprovning avrundas alltid uppåt).

## Validering mot Berghällen (env-gated, körd grön)
Riktiga ritnings-PDF:er → `crow_vent_drawing` → risermodell:
105 strängar hus C+D (35 lgh × 3), trapphuslängder inom 5 % av facit
(200/188/248/248 m), radhus 9 strängar inom 20 % av 63 m med eget top_plan.
Hela den manuella kvantitetskedjan från anbudet är därmed automatiserad.

## Grindar
Ruff 0, mypy strict 0 (218 filer), 461 tester + 3 env-gated skips
(samtliga körda gröna mot riktiga kundfiler i byggmiljön).
