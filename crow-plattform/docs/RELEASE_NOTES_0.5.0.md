# Crow 0.5.0 — Foundation Release

## Betydelse

Detta är Crow Backbones första fungerande version.

"Fungerande" betyder här att Backbonen:

1. kan installeras som ett självständigt Pythonpaket,
2. kan upptäcka en separat domänmodul,
3. kan validera modulens kontrakt och beroendegränser,
4. kan genomföra ett verkligt domänscenario end-to-end,
5. behåller evidens, provenance och granskningsbarhet genom hela beslutskedjan.

Det betyder ännu inte att Crow kan läsa ett komplett PDF-underlag automatiskt. Den förmågan byggs ovanpå denna grund i Sprint B.

## Releasebevis

Crow Vent Reference Module `0.2.0` installerades tillsammans med Backbone som separata wheels i en isolerad virtuell miljö.

Verifierat utfall:

- modulupptäckt via `crow.modules`,
- versionskompatibilitet,
- signerad manifest/trust-referens,
- noll privata Backbone-importer,
- automatiserat authority-beslut,
- accepterad dimension 200 mm,
- kommersiellt delta 3 960 SEK,
- kalkylrad, beställarfråga, reservation och ÄTA opportunity.

## Stabilitetslöfte för 0.5.x

Följande publika områden behandlas som stabila:

- `crow_module_sdk`,
- `crow_module_conformance`,
- plugin entry point `crow.modules`,
- publika modell- och servicekontrakt som används av Crow Vent `0.2.0`.

Defektfixar och additiva förbättringar kan släppas som `0.5.x`. Brytande kontraktsändringar ska inte smygas in i patchreleaser.

## Kända begränsningar

- HMAC-signering är en symmetrisk referensimplementation; extern tredjepartsdistribution kräver asymmetrisk signering.
- Den generiska referenspipelinen hanterar ett begränsat alternativscenario och enkel enhetsprissättning.
- PDF, OCR, ritningssegmentering och AI-extraktion ingår inte.
- Authority-regler måste vara explicita eller bekräftas av människa; Crow uppfinner inte dokumentföreträde.
