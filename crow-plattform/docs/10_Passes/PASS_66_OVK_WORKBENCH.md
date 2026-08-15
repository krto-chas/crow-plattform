# Pass 66 — OVK Workbench

## Syfte

Göra Pass 64–65:s OVK-domän och konservativa dokumentimport synlig och användbar i Workbench utan att införa normtolkning, beständig besiktningslagring eller slutprotokoll i samma pass.

## Implementerat

- Ny `/ovk`-vy i befintlig FastAPI/HTML-Workbench.
- OVK ligger bakom befintlig entitlement-spärr via `/api/ovk`.
- Projekt kan väljas från Workbenchens befintliga projektlista.
- `POST /api/ovk/projects/{project_id}/import-preview` tar evidensrader och bygger riktiga `Observation`/`ObservationCollection`-objekt före import.
- Importresultatet visar system, uttryckligt märkta mätningar, tidigare findings och review-kö.
- PDF-liknande locator byggs av dokument-id, sida och region så källreferens syns i vyn.
- Decimal-värden lämnar API:t som strängar.
- HTML-vyn escapear importerad text innan den renderas.

## Review-princip

Pass 65 kunde tidigare känna igen ett system i en rad som `B1 FTX01 34 l/s 40 l/s` och därmed betrakta raden som delvis mappad, samtidigt som de oetiketterade luftflödena inte syntes i `unmapped`. Pass 66 korrigerar detta: raden kan bidra med system-ID men läggs samtidigt i review med orsaken `unlabelled_airflow_value`.

Detta gör review-kön till en lista över osäker information, inte bara helt okända rader.

## Medvetna avgränsningar

- Ingen automatisk hämtning av persistenta `ObservationCollection` per projekt finns ännu i Workbench. Vyn är därför en import-/review-preview mot samma domänadapter, inte ett påstående om färdig projektpersistens.
- Ingen BFS-/OVK-regeltolkning.
- Ingen automatisk PASS/FAIL från luftflödesavvikelse.
- Ingen redigering/godkännande av review-rader ännu.
- Ingen persistens av OVK-besiktningen.
- Ingen slutlig OVK-protokollexport.

## Acceptance criteria

- `/ovk` är åtkomlig i app-skalet.
- Explicit uppmätta/projekterade luftflöden visas med system, punkt och evidence-ref.
- STATED findings visas utan uppfunnen severity eller åtgärdsplikt.
- Delvis mappad evidens med oetiketterade luftflöden syns i review-kön.
- Tom import avvisas med 422.
- Ruff, mypy strict, pytest, architecture review och distribution build ska vara gröna före merge.
