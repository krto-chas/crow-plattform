# Pass 98 — OVK-ombesiktning

## Mål
Stänga cirkeln efter en underkänd OVK: kedjan underkänd → åtgärder → ombesiktning →
godkänd som spårbart, bevisbart tillstånd i workflow-paketet. EJ GODKÄND-intygets
"ombesiktning krävs"-basis (pass 97) får därmed ett faktiskt flöde att peka på.

## Utökning av `crow_ovk_workflow`: `reinspection.py`
Ombesiktningen är workflow-tillstånd i grunden och ligger därför i det befintliga
paketet — ingen ny paketmigrering, tillståndsmaskinen har en ägare.

### Modeller
- `ReinspectionItem`: ögonblicksbild av en brist (finding-ID, beskrivning, severity,
  system) plus åtgärds- och verifieringstillstånd. Valideringar i `__post_init__`:
  uppgiven åtgärd kräver skriven notering, verifiering kräver ombesiktnings-ID.
- `OvkReinspectionCase`: ärende med källbesiktning, punkter, öppningstid, valfri
  åtgärdsfrist samt `result_inspection_id`/`closed_at` som bara får förekomma i par.
  Härledd status: `open` → `ready` (alla punkter verifierade) → `closed`.

### STATED/OBSERVED-disciplin
- `RemedyState`: `open` → `remedy_claimed` → `verified`/`failed`.
- Byggnadsägarens uppgivna åtgärd är **STATED** (`remedy_origin`), kräver notering och
  kan bära `evidence_ref`. En uppgift är inte en verifiering.
- Funktionskontrollantens verifiering vid ombesiktningen är **OBSERVED** och binds till
  ombesiktningens besiktnings-ID. `failed` kan öppnas igen med ny uppgiven åtgärd.

### Övergångar (immutabla, ärendet returneras nytt)
- `open_case(record, ...)`: kräver protokollklart record med slutsats `DEFICIENCIES`
  och minst en finding med `action_required`; punkterna kopieras som ögonblicksbild så
  ärendet är självbärande (chain of custody).
- `claim_remedy(case, finding_id, note, evidence_ref)`.
- `verify_item(case, finding_id, verified, reinspection_id, note)`.
- `close_case(case, reinspection_record)`: kräver att ombesiktningsrecordet är
  protokollklart och `APPROVED`, inte är källbesiktningen, samt att samtliga punkter är
  verifierade mot exakt det recordets besiktnings-ID. Först då sätts
  `result_inspection_id` + `closed_at`. Ett stängt ärende är oföränderligt.

Payload-roundtrip med schema `crow-ovk-ombesiktning-v0.1` och
`OvkReinspectionRepository` med atomiska skrivningar under
`projects/{project}/ovk-ombesiktning/{case_id}.json`.

## Yta
`ovk_reinspection_surface.py` i `crow_ovk_module`:

- `GET /ovk/ombesiktning` — workbench-sida med punktlista, uppge/verifiera/stäng
- `POST /api/ovk/projects/{p}/inspections/{i}/ombesiktning` — öppna ärende
  (409 `OVK_CASE_NOT_OPENABLE` om recordet inte är protokollklart underkänt)
- `GET .../ombesiktning` och `GET .../ombesiktning/{case_id}` — lista/detalj
- `POST .../{case_id}/remedy`, `POST .../{case_id}/verify` — 422 vid regelbrott
- `POST .../{case_id}/close` — 409 `OVK_CASE_NOT_CLOSABLE` tills allt är verifierat
  mot ett godkänt ombesiktningsrecord

## Koppling till pass 97 och 99
Ombesiktningen är ett vanligt workflowrecord — intyg för den utfärdas som vanligt via
pass 97 när den är godkänd. Pass 99 (bevakningen) kan därmed utgå från ett riktigt
godkänd-datum oavsett om det kom från första förrättningen eller via ett stängt
ombesiktningsärende.

## Ägarskap och gate
Layoutmanifest 1.11: `test_ovk_reinspection.py` i `owned_tests`; ägarskapsvakten
utökad. Gate: `ruff format` → `ruff check` → `mypy --strict` → `pytest`. Tester täcker
öppningsspärrar, noteringskrav, verifieringsbindning, ready/closed-övergångar,
avvisning av fel ombesiktnings-ID och källbesiktning som resultat, payload- och
repository-roundtrip samt ytans hela kedja 200/409/404.
