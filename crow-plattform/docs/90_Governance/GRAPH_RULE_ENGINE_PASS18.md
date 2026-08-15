# Graph Rule Engine — pass 18

## Syfte

Separera Building Graph-data, regeldefinitioner och audit-resultat. Modulen
`crow_graph_rules` är domänoberoende; ventilationsgranskningen använder den som en
profil utan att ändra tidigare finding-format eller granskningsflöden.

## Implementerat

- typad `GraphRuleMetadata`
- typad `GraphRuleContext`
- protokoll för utbytbara `GraphRule`-implementationer
- deterministisk `GraphRuleEngine`
- validering av regel-ID, version, disciplin och severity
- blockering av dubblerade regel-ID:n i samma körning
- metadata som redovisar körda regler och att ingen inferens eller automatisk
  korrigering utförts
- migrering av fyra befintliga ventilationskontroller till separata regler:
  - `VENT-DQ-001`
  - `VENT-DQ-002`
  - `VENT-EVID-001`
  - `VENT-EVID-002`

## Evidensprincip

Regelmotorn ändrar inte grafen. Den gör ingen geometrisk eller AI-baserad inferens.
Saknad information fortsätter att klassificeras som evidensgap och inte som ett
fastställt projekteringsfel.

## Avgränsningar

- inga nya domänregler för VS, EL, sprinkler, brand eller bygg
- ingen extern regelkonfiguration från YAML/JSON
- ingen automatisk korrigering
- ingen Workbench-vy för regelpaket
