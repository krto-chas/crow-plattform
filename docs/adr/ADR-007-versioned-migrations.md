# ADR-007: Versioned migration paths

## Status
Accepted

## Decision
Persisted schemas and contracts use explicit semantic versions. Migrations are registered as directed steps and executed only along a known path.

## Consequences
No implicit or destructive migration is allowed.
