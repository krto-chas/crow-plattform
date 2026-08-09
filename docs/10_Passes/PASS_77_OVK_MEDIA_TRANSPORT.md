# Pass 77 — OVK Media Transport & Evidence Binding

## Scope

Föra fotografisk OVK-evidens från lokal IndexedDB till modulens serverlagring utan att en bild kan markeras som synkad innan de faktiska bildbytesen verifierats.

## Transportkontrakt

1. Fältklienten synkar först sin `FieldInspectionData`-snapshot.
2. Varje lokal mediablob laddas upp till `PUT /api/ovk/field/media/{inspection_id}/{photo_id}`.
3. Servern kräver att `photo_id` redan finns i den accepterade snapshoten.
4. `Content-Type` måste motsvara bildens `mime_type` i snapshoten.
5. Servern beräknar SHA-256 över mottagna bytes och jämför med bildens deklarerade `sha256`.
6. Först efter match skrivs binärfil + kvitto atomiskt och snapshotens `sync_status` ändras till `synced`.
7. Klienten uppdaterar därefter lokal status och skickar en slutlig snapshot så båda sidor konvergerar.

## Evidence binding

Ett accepterat foto får två stabila identifierare:

- `media_id = sha256:<digest>` — innehållsidentitet.
- `evidence_id = ovk-photo:<digest>` — deterministisk bindning av `inspection_id + photo_id + media sha256`.

Det gör att identiska bytes kan kännas igen samtidigt som evidensbindningen fortfarande är specifik för besiktningen och fotoposten.

## Lagring

Servermedia lagras under modulens `data_root/ovk-field-media/<inspection_id>/` som:

- `<photo_id>.bin` — verifierade bildbytes.
- `<photo_id>.json` — kvitto med media/evidence-id, SHA-256, MIME-typ och storlek.

Skrivning sker via temporär fil + atomisk replace. `GET .../media/{inspection_id}/{photo_id}` returnerar kvittot och `GET .../content` returnerar verifierade bytes med ETag och evidence/media headers.

## Säkerhets-/integritetsregler

- Ingen upload accepteras utan föregående snapshot-bindning.
- Hash-mismatch → 409 och ingen mediapost skrivs.
- MIME-mismatch → 415.
- Tom media → 422.
- Media över 25 MiB → 413 som operativ skyddsgräns för fältbilder.
- Path-parametrar valideras med samma säkra identifieringsprincip som övrig OVK-fältpersistens.

## Klient

`Synka data + bilder` kör snapshot → pending media → slutlig snapshot. Bilden ligger kvar i IndexedDB även efter lyckad upload tillsammans med serverns `media_id`, `evidence_id` och `synced_at`, så lokal historik inte förstörs av synk.

## Gate

- Ruff
- root mypy strict
- first-party module mypy strict
- pytest
- architecture review
- distribution build

Regressioner täcker idempotent upload, SHA-256-verifiering, snapshot-bindning, MIME-kontroll, fysisk mediafil, kvitto, snapshotstatus och verifierad nedladdning.
