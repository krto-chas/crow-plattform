# Pass 95 – OVK Test Ownership

## Syfte

Slutföra repository ownership för `crow.ovk` genom att flytta OVK-domänens tester från backbone `tests/` till `modules/crow-ovk-module/tests/`.

## Audit

En importbaserad audit på `main` identifierade 16 root-tester som direkt importerade OVK-ägda paket. Samtliga klassades som modulägda; inget av dem behöver ligga kvar i backbone som plattformsintegration.

## Flyttade tester

- `test_ovk_domain.py`
- `test_ovk_field.py`
- `test_ovk_field_history.py`
- `test_ovk_field_media.py`
- `test_ovk_field_surface.py`
- `test_ovk_field_workbench.py`
- `test_ovk_import.py`
- `test_ovk_legacy.py`
- `test_ovk_legacy_commit.py`
- `test_ovk_module_ownership.py`
- `test_ovk_pricing.py`
- `test_ovk_reporting.py`
- `test_ovk_surface.py`
- `test_ovk_time_capture.py`
- `test_ovk_web_ownership.py`
- `test_ovk_workflow.py`

Filerna flyttas utan ändrad testlogik.

## Manifest

`modules/module_layout_manifest.json` höjs till 1.9. `crow.ovk` får:

- `source_migration_complete: true`
- `test_migration_complete: true`
- `repository_ownership_complete: true`

Efter detta är Vent, Provtryckning och OVK samtliga markerade med komplett repository ownership.

## Permanent gate

Root-auditen verifierar att:

1. samtliga deklarerade OVK-tester finns i OVK-modulens testkatalog,
2. inga av dessa filer finns kvar i root `tests/`,
3. nya root-tester inte direktimporterar OVK-ägda paket.

CI är evidensgaten för Ruff, mypy, modulernas strict-mypy, pytest, architecture review och distribution build.
