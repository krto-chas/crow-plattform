# Pass 60 — Vent produktvy

## Syfte

Göra den befintliga Vent takeoff-/kalkylkedjan åtkomlig som en tydlig produktfunktion ovanpå Pass 59:s app-shell och entitlementmodell, utan att duplicera domänlogik eller introducera ett nytt frontendramverk.

## Implementerat

- `/vent` — separat Vent-produktvy i befintlig FastAPI/HTML-stack.
- Projektval via ordinarie `/api/projects`.
- Mängdförteckning, beskrivningstext och prisbok kan köras från webbvyn.
- `/api/vent/projects/{project_id}/takeoff` — entitlement-skyddat produkt-API som återanvänder den befintliga `/api/projects/{project_id}/takeoff`-kedjan.
- Resultat visas med radantal, prissatta rader, arbetstid och total när motsvarande värden finns i payloaden.
- CSV-export sker i webbläsaren från den returnerade konsoliderade payloaden.

## Medvetna avgränsningar

- Pass 54:s `crow_offer_export` tillhör provtryckningsflödet och används därför inte som Vent-offert.
- Full Vent-offertmodell och offertpresentation byggs i nästa Vent-slice.
- Kallprojekt och DWG-installationshärdning är validerings-/hardeningarbete, inte del av detta pass.
- Den äldre `/api/projects/{project_id}/takeoff` lämnas kvar för bakåtkompatibilitet; produktvyn använder endast entitlement-skyddade `/api/vent/...`.

## Gate

Ruff, mypy strict, pytest, architecture review och distribution build ska vara gröna i CI innan merge.
