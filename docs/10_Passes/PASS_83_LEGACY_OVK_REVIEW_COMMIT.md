# Pass 83 — Legacy OVK Review → Historical Commit

## Scope

Ta godkänd data från Pass 80:s legacy-preview och materialisera den som historisk OVK på servern.

## Princip

Legacy-import får inte bli ny fältevidens. Godkända fakta lagras som historiska poster med explicit källproveniens till originalfilens SHA-256 och locator. Serverhistoriken återanvänder samma snapshot/context-lager som fältbesiktningar men markerar kontexten med `source_kind=legacy_import`.

## API

`POST /api/ovk/legacy/commit`

Payload innehåller:

- `inspection_id`
- `project_id`
- `inspector`
- `inspection_date`
- `source_filename`
- `source_sha256`
- review-godkända `facts` med `source_id`, `locator` och `source_sha256`

Committen avvisas om fakta blandar källhashar. Inspektionsdatum måste vara explicit eller entydigt extraherat.

## Materialisering

- lägenhetsnummer blir historiska enheter,
- anmärkningar blir historiska findings med `legacy_source`,
- system- och luftflödesfakta behålls under snapshotens `legacy`-sektion med full proveniens,
- inga legacy-bilder eller nya evidence-id skapas i detta pass.

`/api/ovk/field/history` exponerar nu även `source_kind` och `inspection_date`, så legacy-import kan användas av samma history/restore-kedja utan att blandas ihop med fältbesiktningar.

## Avgränsning

Passet löser review → commit-kontraktet. Parserprofiler för verkliga historiska protokoll, UI för massgranskning/import och mer exakt koppling mellan mätpunkt, rum och lägenhet byggs mot verkligt arkivmaterial i senare pass.

## Gate

- Ruff
- root mypy strict
- first-party module mypy strict
- pytest
- architecture review
- distribution build
