# Pass 59 — App-shell och entitlements foundation

## Syfte

Införa ett tunt produktskal ovanpå befintlig Crow Workbench utan att bygga om
frontend eller skapa ett parallellt plugin-system. `crow.modules` fortsätter
vara sanningskälla för runtime-plugin discovery. Pass 59 lägger endast till
produktmetadata och kundens rätt att konsumera en modul.

## Implementerat i passet

- Nytt paket `crow_entitlements` med frusna dataklasser för produktmoduler,
  kundkontext och entitlements.
- `product_modules.json` som installationsmetadata för namn, route,
  API-prefix och datamässiga beroenden. `runtime_module_id` kopplar metadata
  till det befintliga `crow.modules`-registret när en riktig plugin finns.
- Databeroenden hålls separata från kommersiella beroenden: Provtryckning,
  OVK och framtida Injustering använder `vent_model`, men kräver inte köp av
  Vent eller OVK.
- Filbaserade kund-entitlements under
  `config/customers/<customer_id>/entitlements.json`; saknad fil betyder inga
  aktiva moduler (fail closed). `valid_until` stöds.
- Kundkontext från miljö. Lokal körning får explicit lokal fallback; serverläge
  kräver `CROW_CUSTOMER_ID` och fallerar stängt om den saknas.
- `GET /api/me/modules` returnerar endast aktiva, ej utgångna produktmoduler.
- Central middleware spärrar modul-API-prefix i backend. Delade Workbench-API:n
  som projekt/import ligger utanför spärren.
- Nytt `crow_workbench.shell` omsluter befintlig Workbench. CLI:n startar nu
  skalet; den stora befintliga `app.py` ändras inte.

## Medvetna avgränsningar

- Ingen full autentisering/JWT/OIDC i detta pass.
- Ingen adminpanel eller PUT-endpoint för entitlement-redigering.
- Ingen IDOR-/signerad-download-ombyggnad; det hör till nästa säkerhetspass.
- Ingen Next.js-migrering. Repo använder idag FastAPI + statisk Workbench och
  Pass 59 följer den faktiska arkitekturen.
- Injustering är `planned` och exponeras aldrig via `/api/me/modules`.
- Benchmark är stöd/capability inom kalkylflödet, inte en egen huvudmodul.

## Acceptance

- Produktmetadata kan laddas deterministiskt.
- Saknad/utgången entitlement ger 403 på modul-API.
- Aktiv entitlement släpper igenom befintlig Vent-route.
- Delade API:n fungerar utan modul-entitlement.
- Serverläge utan kundidentitet ger kontrollerat 503-fel.
- Ruff, mypy strict, pytest, architecture review och build ska verifieras i CI
  innan merge.
