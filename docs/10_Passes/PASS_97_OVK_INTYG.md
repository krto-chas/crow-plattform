# Pass 97 — OVK-intyg

## Mål
Göra OVK-leveransen juridiskt komplett: efter godkänt protokoll ska plattformen kunna
utfärda det intyg som byggnadens ägare enligt plan- och bygglagstiftningen ska anslå på
väl synlig plats i byggnaden.

## Nytt paket: `crow_ovk_intyg`
- `models.py`: frusna dataklasser för `OvkIntyg`, `Funktionskontrollant` (behörighet N/K,
  certifieringsorgan, certifikatnummer, giltighetstid), `Byggnadsagare`, `IntygSystemRow`
  och `NextInspection`. Valideringar i `__post_init__`: obligatoriskt intygs-ID och
  fastighetsbeteckning, utfärdandedatum får inte föregå besiktningsdatum, härledd frist
  kräver skriven basis.
- `service.py`: `build_intyg` bygger intyget ur ett sparat `OvkWorkflowRecord` och vägrar
  om workflowet inte är protokollklart — samma spärr som protokollet, så intyg aldrig kan
  utfärdas före godkänd review. Slutsatsen mappas deterministiskt:
  `APPROVED → GODKÄND`, `DEFICIENCIES → EJ GODKÄND`. Systemrader markeras EJ GODKÄND
  om de har bundna findings med `action_required`.
- Payload-roundtrip (`intyg_to_payload`/`intyg_from_payload`) med ISO-datum och
  schema-version `crow-ovk-intyg-v0.1`.
- `repository.py`: atomiska skrivningar, säkra identifierare, sökväg
  `projects/{project}/ovk-intyg/{intyg_id}.json`.
- `anslag.py`: `intyg_html` renderar anslagsversionen på svenska med resultatruta,
  kontrollantuppgifter, systemtabell och fotnot som märker fristen som härledd uppgift.

## STATED/INFERRED-disciplin
Nästa besiktningsfrist är alltid en härledd uppgift och bär obligatorisk skriven basis:

- GODKÄND: kortaste återkommande intervall enligt BFS 2011:16 hämtas ur den befintliga
  OVK-taxans intervallregler (`crow_ovk_pricing.OvkTaxa.recurring_interval_years`) per
  registrerad systemtyp; frist = besiktningsdatum + intervall (skottdagssäkert).
  Basis anger datum, intervall, byggnadskategori och systemtyper.
- Småhus eller okända systemtyper: ingen frist, med basis som förklarar varför.
- EJ GODKÄND: ingen frist; basis anger att ombesiktning krävs efter åtgärder. Det är
  förberedelsen för pass 98 (ombesiktningsflödet), som knyter an här.

Intervallreglerna har därmed en enda källa (taxa-lexikonet) — ingen duplicering.

## Yta
`ovk_intyg_surface.py` i `crow_ovk_module`:

- `GET /ovk/intyg` — workbench-sida för utfärdande
- `POST /api/ovk/projects/{p}/inspections/{i}/intyg` — bygger ur sparat workflowrecord,
  409 `OVK_INTYG_NOT_READY` om workflowet inte är protokollklart, 404 om besiktningen
  saknas, 422 vid ogiltiga fält
- `GET /api/ovk/projects/{p}/intyg` — lista
- `GET /api/ovk/projects/{p}/intyg/{id}` — payload
- `GET /api/ovk/projects/{p}/intyg/{id}/anslag` — anslags-HTML

Pluginen registrerar routern och exporten `ovk_intyg`.

## Ägarskap och vakter
- Layoutmanifest 1.10: `crow_ovk_intyg` i `owned_packages`/`migrated_packages`,
  `test_ovk_intyg.py` i `owned_tests`.
- `tests/test_ovk_test_ownership_audit.py` utökad med paketet och testfilen.
- `known-first-party` och modulens package-data (`py.typed`) uppdaterade.

## Gate
`ruff format` → `ruff check` → `mypy --strict` (modulkällkod och modultester) → `pytest`.
Tester täcker godkänd/ej godkänd, kortaste intervall över flera system, småhus utan frist,
review-spärr, payload- och repository-roundtrip, anslagsrendering samt ytans 200/409/404.
