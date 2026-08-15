# Crow Building Graph RC1 – Sprint 1

## Status

Implementerad och testad grafkärna för Crow Platform 2.0.

## Levererat

- Gemensam identitetsmodell för grafobjekt.
- Evidens som förstaklassobjekt med källa, locator, checksumma och confidence.
- Egenskaper med värde, enhet, evidens och revision.
- Riktade relationer med standardiserade relationstyper och egen evidens.
- Oföränderlig historik för skapande och ändringar.
- Atomisk JSON-persistens per projekt.
- Neighbor-query för direkt graftraversering.
- Workbench API för grafens kärnoperationer.

## Avgränsning

Sprint 1 innehåller ingen byggnadshierarki eller Vent-migrering. Dessa hör till Sprint 2
respektive senare adapterarbete. Grafkärnan är medvetet domänneutral.
