# Pass 73 — OVK Field + Workflow Ownership Migration

## Syfte

Fortsätta den fysiska modulgränsen från Pass 72 genom att flytta OVK:s fältdomän och besiktningsworkflow från backbone `src/` till `modules/crow-ovk-module`.

## Ändring

- `crow_ovk_field` ägs och distribueras nu av `crow-ovk-module`.
- `defect_types.json` följer med fältpaketet som modulägd installationsdata.
- `crow_ovk_workflow` ägs och distribueras nu av `crow-ovk-module`.
- Publika importnamn är oförändrade: `crow_ovk_field` och `crow_ovk_workflow`.
- Rootpaketet slutar paketera och strict-mypy-kontrollera dessa två paket; modulens separata CI-gate gör det i stället.
- Ruff klassificerar de flyttade paketen som first-party trots fysisk placering under `modules/`.

## Ej i detta pass

- `crow_ovk_import`, `crow_ovk_pricing` och Workbench-ytornas fysiska ägarskap flyttas inte här.
- `crow_regulations` ligger kvar i plattformen eftersom regelbiblioteket är en gemensam capability och inte endast OVK-data.
- Ingen funktionell offline- eller synkfunktion läggs till.

## Gate

Passet är endast mergeklart när rootinstallation + förstapartsmoduler kan installeras och Ruff, root mypy strict, modul-mypy strict, pytest, architecture review och distribution build är gröna.
