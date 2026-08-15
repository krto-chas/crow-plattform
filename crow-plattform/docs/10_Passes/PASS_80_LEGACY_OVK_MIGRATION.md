# Pass 80 — Legacy OVK Migration Framework

## Scope

Göra äldre OVK-protokoll till förstaklassiga historiska källor utan att anta att Crow skapade originalbesiktningen.

Första versionen läser `.pdf` och `.xlsx`, klassificerar källan, räknar SHA-256 och producerar en preview med explicit extraherade fakta samt reviewposter för tvetydig data.

## Proveniens

Varje extraherat faktum bär:

- originalfil,
- filtyp,
- källfilens SHA-256,
- stabilt `source_id`,
- PDF-sida/rad eller Excel-blad/cellintervall.

Originalfilens information omvandlas inte direkt till ny OVK-evidens. Preview/review sker först.

## Första explicit stödda fakta

- besiktningsdatum,
- ventilationssystem-ID,
- lägenhetsnummer när det uttryckligen är märkt,
- uppmätt luftflöde när värdet uttryckligen är märkt,
- projekterat/börvärde när det uttryckligen är märkt,
- anmärkning/brist när den uttryckligen är märkt.

Oetiketterade luftflöden skickas till review i stället för att Crow gissar kolumnsemantik.

## API

`POST /api/ovk/legacy/preview`

Multipart:

- `project_id`
- `file`

Svaret innehåller `facts`, `review`, `source_sha256` och `ready_for_commit`.

## Avgränsning

Detta pass är ett migrationsramverk, inte löftet att alla historiska protokollvarianter redan stöds. Nästa steg är parserprofiler baserade på verkliga PDF-/Excelmallar från arkivet, korsvalidering när samma besiktning finns i flera format samt ett explicit review/commit-flöde till fastighetens OVK-historik.

`.xls` stöds inte i denna version och avvisas uttryckligen; formatet ska få en egen adapter om verkligt arkivmaterial kräver det.

## Gate

- Ruff
- root mypy strict
- first-party module mypy strict
- pytest
- architecture review
- distribution build
