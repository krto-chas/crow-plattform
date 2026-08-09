# Pass 71 — Module Boundary Consolidation

## Syfte

Återställa den avsedda backbone-principen: verksamhetsmoduler ska kunna jackas på Crow utan att `crow_workbench.shell` behöver känna till varje modul med hårdkodade imports.

## Implementerad gräns

- `crow_module_sdk.web.CrowWebModule` är ett valfritt kontrakt för moduler som exponerar Workbench-routes.
- `crow_workbench.shell` upptäcker installerade `crow.modules` via `ModuleRegistry` och monterar routers dynamiskt.
- Vent, Provtryckning och OVK exponeras som installerbara förstapartsmoduler under `modules/`.
- CI installerar och strict-type-checkar samtliga förstapartsmoduler.
- Ett modul-test låser att Vent, Provtryckning och OVK kan upptäckas och att deras produkt-routes monteras utan hårdkodning i shell.

## Medveten migrationsgräns

Domänimplementationerna (`crow_ovk*`, `crow_pressure_test*` och delar av `crow_vent*`) ligger fortfarande under root `src/` som kompatibilitetskod. Pass 71 flyttar ägarskap/integration och tar bort Workbench-shellens direkta kännedom om modulerna, men raderar inte kompatibilitetspaketen i samma pass. Fysisk utflyttning görs först när importberoendena kan brytas utan att skapa parallella implementationer.

Detta är avsiktligt: inga imports eller tester ska brytas bara för katalogestetik. Slutmålet är att modulernas interna domänpaket också ägs av respektive `modules/crow-*-module`, medan gemensamma kapabiliteter såsom regulations, evidence, entitlement och module SDK stannar i plattformens `src/`.

## Gate

Passet är inte verifierat förrän Ruff, root mypy strict, modulernas mypy strict, pytest, architecture review och distribution build är gröna i GitHub Actions.
