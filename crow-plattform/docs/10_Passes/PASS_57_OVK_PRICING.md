# Pass 57 — OVK-prissättning (`crow_ovk_pricing`)

> Numrering: Pass 51–56 är reserverade av provtryckningssviten
> (levererad som gren-zippar, ej mergad till main vid detta pass).
> Detta pass tar därför nästa fria nummer, 57.

## Syfte

Prissätta OVK-besiktningar enligt branschpraxis, med besiktningstyp och
objektstorlek som användarens val:

| Objektkategori | Prisgrund | Storlek |
| --- | --- | --- |
| Flerbostadshus | pris per lägenhet | obligatorisk (antal lgh) |
| En- och tvåbostadshus (småhus) | fast pris per hus | frivillig, påverkar ej pris |
| Hotell, vandrarhem och liknande | pris per rum | obligatorisk (antal rum) |
| Lokaler, kontor, industri, skolor, vård m.m. | pris per m², à-pris per systemtyp (S/F/FX/FT/FTX) | obligatorisk (area + systemtyp) |

En förfrågan består av en eller flera **delposter** med samma
besiktningstyp — t.ex. ett hotell med rum per styck och
restaurang/konferens per m² — som prissätts i en gemensam kvot där
varje delpost blir en egen rad med egen prisgrund, egen frivillig
benämning och egen intervallupplysning. Kvoten bär det kortaste kända
intervallet över delposterna (`next_inspection_interval_years`).

Utöver radpriserna finns en **grundavgift** per uppdrag (etablering,
protokoll, intygshantering) som adderas en gång per uppdrag oavsett antal delposter, och en
**minimidebitering** som golv för totalen så att små objekt inte
prissätts orimligt lågt. När golvet slår till flaggas det i kvoten
(`minimum_applied`) — kvoten döljer aldrig varför totalen ser ut som
den gör.

## Regelkunskap ur BFS 2011:16

- Småhus omfattas endast av förstagångsbesiktning; en begäran om
  återkommande besiktning för småhus avvisas med tydligt fel i stället
  för att prissättas fel.
- Kvoten bär intervallupplysning (`recurring_interval_years`):
  förskolor/skolor/vårdlokaler 3 år oavsett systemtyp, FT/FTX 3 år,
  S/F/FX 6 år, småhus `None`. Utan känd systemtyp returneras `None` —
  Crow gissar inte intervall.

## Arkitektur

- `models.py` — StrEnum-typer (besiktningstyp, kategori, systemtyp,
  prisgrund) och frusna slots-dataklasser för förfrågan, rad och kvot.
- `taxa.py` — `OvkTaxa` laddar `ovk_taxa_lexikon.json` via
  `importlib.resources`; à-priser, grundavgift, minimidebitering och
  intervalltabell har en enda källa. Beloppen i det medföljande
  lexikonet är exempeltaxa (installationsdata) — varje installation
  ersätter dem med sin egen prislista; regelverket är kunskap.
- `quote.py` — `build_quote` validerar storlekskrav per prisgrund,
  räknar med `Decimal` hela vägen (ören, ROUND_HALF_UP) och är
  deterministisk: samma förfrågan och taxa ger samma kvot.
  `quote_to_payload` serialiserar belopp som strängar (ADR-0009-andan).

Paketet är rent: inga beroenden utanför standardbiblioteket, ingen
PDF- eller UI-koppling. Framtida integration: systemtypen kan föreslås
ur senaste OVK-protokollet (E1-extraktionen i `crow_ovk`, gren-zip) vid
återkommande besiktning, och kvoten kan exporteras via
offertkedjan/Workbench.

## Avgränsningar

- Ett prisband per systemtyp; storleksberoende m²-trappa
  (sjunkande à-pris för stora objekt) är medvetet framtida arbete och
  ryms i lexikonformatet utan schemabrott.
- Ombesiktning efter underkänd OVK och tillägg (t.ex. luftflödesmätning
  utanför OVK-kravet) prissätts inte här ännu.

## Grindar

Ruff 0, mypy strict 0, hela testsviten grön inklusive 20 nya tester
(prisgrunder inkl. hotell per rum, kombinerade delposter (hotell + restaurang, bostad + butik), valideringsregler, minimidebitering, grundavgift,
intervalltabell, determinism, payload-serialisering, lexikontäckning).
