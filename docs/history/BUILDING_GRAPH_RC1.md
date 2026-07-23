# Crow Building Graph 1.0 RC1

RC1 sammanför grafkärna, byggnadsstruktur, systemgraf och komponentgraf till en gemensam informationsmodell.

## Lager

1. Graph Core: CrowObject, CrowRelation, CrowProperty, CrowEvidence och CrowHistory.
2. Building Structure: building, floor, space och zone.
3. System Graph: domänneutrala tekniska system.
4. Component Graph: domänneutrala tekniska komponenter.
5. Integration: integritetskontroll, generell traversal och portabel RC1-snapshot.

## Sanningsmodell

Ritningar och importer är evidenskällor. Building Graph är den normaliserade projektsanningen. Kunskapspaket, exempelvis Crow Vent, konsumerar och berikar grafen utan att skapa parallella byggnadsmodeller.

## RC1-kriterier

- Alla relationers ändpunkter ska finnas.
- Alla evidensreferenser ska kunna lösas.
- Alla egenskaper ska ha en existerande ägare.
- Fel gör grafen ogiltig; granskningsvarningar stoppar inte export.
- Snapshotformat: `crow-building-graph-1.0-rc1`.
