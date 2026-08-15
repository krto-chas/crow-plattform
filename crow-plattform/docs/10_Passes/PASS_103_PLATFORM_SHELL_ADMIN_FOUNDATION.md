# Pass 103 — Platform shell & admin foundation

## Syfte

Göra Crow Platform till den faktiska produktstartytan i stället för att låta en
enskild domänmodul vara startsida. Passet bygger vidare på Pass 59-entitlements
och den manifestdrivna moduldeploymenten utan att införa ett parallellt
modulsystem.

## Omfattning

- `/` blir ett tunt Platform-shell som väljer mål utifrån aktuell identitet.
- Vanlig kundkontext får `/app`; rollen `platform-admin` får `/admin`.
- Den tidigare Workbench-startytan bevaras på `/workbench`.
- `/app` bygger modulvalet från befintliga `/api/me/modules`, alltså från kundens
  aktiva entitlements och produktkatalogen.
- `/admin` visar produktmoduler, kopplad runtime-modulstatus och konfigurerade kunder.
- Admin-API kan läsa och atomiskt uppdatera
  `config/customers/<customer_id>/entitlements.json`.
- Admin-skrivning validerar okända moduler, planned-moduler och kommersiella
  modulberoenden innan filen ändras.
- Admin-API kräver explicit rollen `platform-admin`; frånvaro av riktig auth ersätts
  inte med en osäker fallback.
- Produktkatalogen kopplar nu Vent, Provtryckning och OVK till deras faktiska
  `crow.modules` runtime-id:n.

## Arkitekturgräns

Detta är management- och shell-grunden, inte ett fullständigt IAM-system. Den
nuvarande identiteten kommer fortfarande från den befintliga miljöbaserade
`CustomerContext`. Riktig login, sessioner, lösenord/OIDC och användarregister ska
läggas ovanpå samma roll- och destinationsmodell i ett separat pass.

Teknisk modulinstallation, runtime-discovery och kommersiell kundåtkomst förblir
separata begrepp:

1. `modules/module_layout_manifest.json` avgör vilka first-party-paket som deployas.
2. `crow.modules` avgör vilka runtime-pluginer som faktiskt kan upptäckas.
3. `product_modules.json` beskriver produkten och dess routes/beroenden.
4. kundens `entitlements.json` avgör vilka produktmoduler kunden får använda.

## Acceptance

- Root visar Platform-shell, inte Vent/Workbench direkt.
- Befintlig Workbench finns kvar på `/workbench`.
- Kund och admin får olika destinationsyta via `/api/session`.
- Admin-API är 403-skyddat utan `platform-admin`.
- Admin kan ändra en kunds entitlements och ändringen kan läsas tillbaka.
- Ogiltiga produktberoenden stoppas innan skrivning.
- Kundens modulkort hämtas från befintlig entitlementmodell.
- Ruff format/check, mypy strict, pytest, architecture review och build är CI-gates.
