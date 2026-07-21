# Crow Architectural Style

Detta dokument beskriver hur en typisk Crow-modul ska kännas igen i kod och beteende.

## En Crow-modul är

- avgränsad till ett tydligt domänansvar,
- byggd kring immutabla modeller,
- deterministisk för samma input och regelversion,
- explicit validerad,
- fri från dolt globalt tillstånd,
- spårbar genom provenance och fingerprints,
- åtkomlig genom en liten publik API-yta,
- testbar utan produktionsinfrastruktur,
- kompatibilitetsmedveten,
- dokumenterad som en del av leveransen.

## Standardstruktur

```text
crow_<capability>/
├── __init__.py
├── models.py
├── engine.py
├── service.py
└── py.typed
```

Ytterligare filer får införas när ansvaret kräver det, men uppdelningen mellan modell, motor och orkestrering ska förbli tydlig.

## Kodstil

- Named domain types prioriteras framför anonyma dictionaries.
- Enum eller Literal används för slutna tillstånd.
- Decimal används för monetära belopp.
- Tidsvärden injiceras när de påverkar resultatet.
- Sortering görs explicit före fingerprinting och serialisering.
- Felmeddelanden ska ange vilket invariant som brutits.
- Publika funktioner exporteras medvetet genom `__init__.py`.

## Beteendestil

En Crow-motor ska kunna beskrivas med:

```text
input → validation → rule evaluation → output → reconciliation
```

Den ska inte:

- skriva filer direkt om detta hör till service-lagret,
- göra nätverksanrop under domänberäkningen,
- ändra inputobjekt,
- använda AI-output som implicit authority,
- fatta ett beslut när underlaget inte uppfyller invariants.

## Granskningsfrågor

Vid review av en ny modul ska följande kunna besvaras:

1. Vilket domänproblem äger modulen?
2. Vilken input accepterar den och vilken output producerar den?
3. Vilka invariants gäller?
4. Hur skapas provenance?
5. Hur säkerställs determinism?
6. Vilka fel är förväntade och hur representeras de?
7. Vilka publika kontrakt exponeras?
8. Vilken authorization krävs?
9. Hur kan modulen reproduceras från sparade artefakter?
10. Vilka tester bevisar dess viktigaste egenskaper?
