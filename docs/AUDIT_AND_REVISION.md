# Audit Events och dokumentrevision

Alla väsentliga projektoperationer skapar oföränderliga audit events med:

- event-ID,
- projektreferens,
- händelsetyp,
- tidpunkt,
- aktör,
- strukturerade detaljer.

När ett dokument får ny revision eller checksumma:

1. dokumentposten uppdateras,
2. Claims från dokumentet markeras invalidated,
3. tidigare körningar som beror på dessa Claims markeras invalidated,
4. projektet återgår till `Draft`,
5. audit events skapas,
6. nya Claims måste extraheras innan projektet kan markeras `Ready`.

Detta förhindrar att gamla beslut lever vidare efter att källunderlaget ändrats.
