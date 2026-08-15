# Vent Audit Finding Review

En finding från en sparad grafgranskning ändras aldrig i efterhand. Ett manuellt beslut
lagras som en separat granskningspost med referens till `audit_id`, `finding_id` och den
grafchecksumma som låg till grund för granskningen.

Tillåtna beslut är:

- `acknowledge` – informationsluckan eller datakvalitetsavvikelsen är mottagen.
- `mark_resolved` – granskaren bedömer att avvikelsen har hanterats utanför den sparade körningen.
- `dismiss` – granskaren bedömer att findingen inte ska drivas vidare.

Beslutet kräver granskare och motivering. Varken grafen, granskningskörningen eller
findingen korrigeras automatiskt. En ny grafstatus måste granskas i en ny audit-körning.
