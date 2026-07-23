# Sprint B1.2 — Intake Reliability

Version: `0.6.0-alpha.2`

B1.2 gör dokumentintaget robust nog för verkliga batcher.

## Implementerat

- beständiga importsessioner,
- strukturerat resultat per fil,
- felisolering: en trasig PDF stoppar inte batchen,
- idempotent återimport,
- förbättrad revisionsordning för A/B, 1/2/10 och 2A/2B,
- koppling mellan dokument och importsession,
- regelbaserad dokumentgraf,
- summering av importfel och relationer,
- bakåtkompatibel laddning av B1-index utan importsessioner.

## Resultatmodell

```text
ImportSession
├── ImportItemResult: imported
├── ImportItemResult: duplicate
├── ImportItemResult: revision
├── ImportItemResult: older_revision
└── ImportItemResult: failed
```

## Dokumentrelationer

B1.2 skapar försiktiga, regelbaserade relationer:

- `AUTHORITY → PRIMARY`: `governs`
- `PRIMARY → REFERENCE`: `references`
- `TECHNICAL_SPECIFICATION → DRAWING`: `describes`

Relationerna är observationer med confidence, inte authority-beslut.
