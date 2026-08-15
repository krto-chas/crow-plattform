# Pass 76 — OVK Offline Field Persistence

## Scope

Göra OVK-fältläget uthålligt vid nätbortfall utan att ändra OVK:s evidensmodell eller påstå att media är synkat när endast metadata har nått servern.

## Klient

- Fältappen paketeras som modulägda HTML/JS-assets.
- Service worker cachar app-shell och feltypslexikon efter första online-laddningen.
- IndexedDB lagrar besiktningsutkast separat från bildblobbar.
- Varje domänmutation sparar lokalt; senaste utkast kan återställas efter omladdning.
- Nätstatus visas i fältvyn.
- Vid återkomst online kan ett smutsigt utkast synkas automatiskt, och manuell synk finns kvar.

## Server-snapshot

`PUT /api/ovk/field/sync/{inspection_id}` validerar samma `FieldInspectionData` som den befintliga valideringsytan och skriver därefter en normaliserad, kanoniskt serialiserad snapshot under modulens `data_root`.

Samma normaliserade payload ska ge samma `snapshot_sha256`. Skrivningen sker via temporär fil + replace.

`GET /api/ovk/field/sync/{inspection_id}` exponerar den senast accepterade snapshoten och dess kvitto.

## Mediagräns

Bildblobbar lagras lokalt i IndexedDB och metadata behåller `sync_status=local`. Snapshot-synk returnerar `media_pending`; den får inte ändra media till `synced` eftersom binär mediatransport inte ingår i detta pass.

## Gate

- Ruff
- root mypy strict
- first-party module mypy strict
- pytest
- architecture review
- distribution build

Regressioner ska täcka offline-assets, service-worker-scope, befintlig fältvalidering, deterministiskt sync-kvitto, fysisk snapshot och identifieringsmismatch.
