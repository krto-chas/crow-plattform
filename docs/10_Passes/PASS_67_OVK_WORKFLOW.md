# Pass 67 — OVK-besiktningsworkflow, persistens och protokoll

## Syfte

Föra OVK från importförhandsgranskning till en sparad, granskningsbar besiktning i Workbench utan att införa normativa regler som inte finns i domänlagret.

## Implementerat

- Nytt typat paket `crow_ovk_workflow`.
- Filbaserad persistens per projekt och besiktning under Workbench-data.
- Atomisk JSON-skrivning via tempfil + replace.
- Validerade projekt-/besiktnings-ID:n för att förhindra path traversal.
- Reviewbeslut med `pending`, `accepted` och `rejected` samt reviewer/note.
- En besiktning utan kontrollpunkter behandlas som `pending` i workflowlagret.
- Protokoll är blockerat om besiktningen är pending eller review-kön innehåller obeslutade poster.
- Printbar HTML-protokollexport från exakt det sparade recordet; exporten räknar eller tolkar inte om resultatet.
- Workbench-yta `/ovk/besiktning` för sparning/laddning av besiktningsutkast.
- API för listning, hämtning, sparning och protokollvisning.

## API

- `GET /api/ovk/projects/{project_id}/inspections`
- `GET /api/ovk/projects/{project_id}/inspections/{inspection_id}`
- `PUT /api/ovk/projects/{project_id}/inspections/{inspection_id}`
- `GET /api/ovk/projects/{project_id}/inspections/{inspection_id}/protocol`

## Evidens- och säkerhetsprincip

- Route-parametrarna är auktoritativa för `project_id` och `inspection_id`; klientpayload får inte byta ägarskap genom att skicka andra ID:n.
- Persistensen innehåller domänens `origin`/`evidence_ref` och reviewbeslut.
- Printprotokollet exporterar sparat resultat och lägger inte till BFS-tolkning, toleransgränser eller annan branschpraxis.
- Protokollexport returnerar 409 om workflow inte är protokollklart.

## Medvetna avgränsningar

- HTML-protokollet är printbart men är inte en genererad PDF.
- Ingen digital signering eller besiktningsmannabehörighet ännu.
- Ingen normmotor/BFS-bedömning i detta pass.
- Workbench-vyn har enkel textinmatning för första workflow-slicen; full fält-UI kommer senare.

## Acceptance criteria

- Sparat record kan laddas deterministiskt utan precisionstapp.
- Tom kontrollpunktslista ger pending, inte approved.
- Obeslutad review blockerar protokoll.
- Komplett explicit godkänd kontroll + avgjord review ger protokollklart record.
- Route-projekt-ID skriver över eventuellt projekt-ID i inkommande payload.
- Protokollet genereras från det sparade recordet och blockeras annars med 409.
- Ruff, mypy strict, pytest, architecture review och distribution build ska vara gröna före merge.
