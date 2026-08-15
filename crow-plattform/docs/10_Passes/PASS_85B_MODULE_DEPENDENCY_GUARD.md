# Pass 85B — Module dependency guard

## Syfte

Låsa modulberoenden som maskinläsbara kontrakt efter Pass 85:s repository-layoutaudit.

## Beslut

- `crow.provtryckning` kräver `crow.vent`.
- Produktmodulen `provtryckning` kräver entitlement för `vent`.
- `crow.ovk` har inget modulberoende.
- `injustering` är planerad och kräver `ovk`.
- Modulberoenden deklareras i både repository-layoutmanifestet och produktkatalogen.
- `/api/me/modules` visar endast moduler vars egna entitlement och samtliga `requires_modules` är aktiva.
- Modul-API spärras med 403 om ett obligatoriskt modulberoende saknas.

## Gate

- Layoutmanifestets beroenden får endast referera deklarerade first-party-moduler.
- En modul får inte kräva sig själv.
- Provtryckningens Vent-beroende och OVK:s avsaknad av modulberoende är regressionstestade.
