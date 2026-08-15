# Pass 82 — OVK Automatic Time Capture + Workbench Adjustment UI

## Scope

Koppla Pass 81:s kanoniska tidsledger till verkligt arbete i fält och Workbench utan att skriva över originaltid.

## FIELD

Fältappen laddar ett separat timer-companion-script. Start av fältläge startar FIELD-tid om ingen timer redan pågår. Timern kan även startas/stoppas manuellt.

Aktiv timer och avslutade, ännu osynkade segment sparas lokalt på fältenheten. Avslutade segment får stabilt `segment_id` och skickas idempotent till servern vid synk eller när nätet återkommer.

## REVIEW / PROTOCOL

Ny modulägd yta: `/ovk/tid`.

Där kan användaren:

- läsa tidsledger för en besiktning,
- starta/stoppa REVIEW-segment,
- starta/stoppa PROTOCOL-segment,
- lägga till manuell +/- justering med obligatorisk orsak och användare.

## API

- `POST /api/ovk/reporting/time/{inspection_id}/segments`
- `POST /api/ovk/reporting/time/{inspection_id}/adjustments`

Append-operationerna är idempotenta på klientens segment-/adjustment-ID. Ett befintligt ledger får inte byta projekt eller besiktningsdatum genom senare append.

## Evidens och spårbarhet

Automatiskt beräknad tid och manuell justering är separata datatyper. `reported_hours` beräknas från segment + adjustments; den automatiska tiden skrivs aldrig över.

## Avgränsning

Detta pass mäter aktiv användartid genom explicita start/stopp-sessioner. Automatisk idle-detektering, bakgrundstimer över operativsystemets app-livscykel och direktinlämning till certifieringsorgan ingår inte.

## Gate

- Ruff
- root mypy strict
- first-party module mypy strict
- pytest
- architecture review
- distribution build
