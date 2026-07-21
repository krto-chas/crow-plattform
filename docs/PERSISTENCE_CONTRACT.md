# Persistence Contract v1.0

Sprint A definierar domänneutrala persistensgränssnitt för:

- Decision Graph,
- computation fingerprints.

Referensimplementationerna använder JSON och versionsmärker formatet med
`schema_version: 1.0`.

Backbone-kod ska bero på repository-kontrakten och inte direkt på JSON, SQL eller en
specifik grafdatabas. Senare implementationer kan därför använda PostgreSQL, Neo4j eller
annan lagring utan att modulkontraktet ändras.
