# Pass 81 — OVK Time Ledger & Certification Reporting

## Scope

Inför ett spårbart tidunderlag per OVK-besiktning och ett första certifieringsrapportlager.

## Tidsmodell

Tid sparas som separata segment:

- `field`
- `review`
- `protocol`

Varje segment har start- och sluttid. Beräknad tid skrivs aldrig över av en manuell ändring.

Manuell korrigering sparas separat med:

- +/- timmar,
- orsak,
- ändrad av,
- ändringstid.

`reported_hours = calculated_hours + adjustments`, dock aldrig under 0 timmar.

## Certifieringsprofil

Rapportperioden är explicit och antas inte vara kalenderår. Profilen innehåller certifieringsorgan, certifikatsnummer, behörighet och periodens start/slut.

## API

- `PUT /api/ovk/reporting/time/{inspection_id}` — spara tidsledger
- `GET /api/ovk/reporting/time/{inspection_id}` — visa beräknad och rapporterad tid
- `PUT /api/ovk/reporting/certification/{profile_id}` — spara certifieringsprofil
- `GET /api/ovk/reporting/annual/{profile_id}` — års-/periodrapport som JSON
- `GET /api/ovk/reporting/annual/{profile_id}.csv` — export som CSV

## Avgränsning

Detta pass bygger den kanoniska tids- och rapportmodellen. Automatisk UI-timer ska kopplas till fält-/review-/protokollaktivitet i ett uppföljande pass så att tidssegment kan samlas offline och synkas utan att nät krävs.

Direktinlämning till certifieringsorgan implementeras inte utan ett verifierat och tillåtet integrationsformat. Adaptergräns för Kiwa/RISE eller andra organ byggs när respektive leveranssätt är verifierat.

## TODO

- Koppla offline-timer till fältappen och visa beräknad tid när besiktningen avslutas.
- Tillåt manuell +/- justering i Workbench med obligatorisk orsak.
- Lägg fortbildning som separat rapportdel när rapportformatet definieras.
- Verifiera Kiwa/RISE:s aktuella mallar/portalflöden och bygg adapter per certifieringsorgan.
- Exportera PDF/XLSX när formatkraven är verifierade; CSV/JSON är neutral bas.

## Gate

- Ruff
- root mypy strict
- first-party module mypy strict
- pytest
- architecture review
- distribution build
