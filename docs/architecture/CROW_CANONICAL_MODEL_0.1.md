# Crow Canonical Model 0.1

CCM är ett deterministiskt normaliseringslager mellan import/tolkning och Building Graph.

## Avgränsning i denna etapp

- Ventilationsobjekt från `VentTextInterpretation` kan översättas till typade CCM-objekt.
- Okänd text skapar inget kanoniskt objekt.
- Varje CCM-objekt bär confidence, status, granskningsorsaker och källevidens.
- CCM-objekt kan skrivas till Building Graph med samma evidens kopplad till både objekt och egenskaper.

## Typer

- `air_handling_unit`
- `fan`
- `duct`
- `damper`
- `silencer`
- `air_terminal`
- `heat_exchanger`
- `air_treatment_component`
- `accessory`

## Ej implementerat

- Geometrisk DWG/IFC-normalisering.
- Automatisk relationsskapning mellan komponenter.
- Dubblettsammanfogning mellan flera källor.
- Fullständig domänmodell för rum, byggnadsdelar och installationer.
