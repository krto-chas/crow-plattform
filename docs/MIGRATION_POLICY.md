# Contract and Persistence Migration Policy

1. Every persisted format has an explicit `schema_version`.
2. Versions follow semantic versioning.
3. A migration must declare one source and one newer target version.
4. Downgrades are not automatic.
5. No migration may silently discard domain evidence, provenance or audit data.
6. Migration execution requires a complete registered path.
7. Migrations must be deterministic and covered by golden or snapshot tests.
8. Major-version changes require an ADR and architecture review.
9. Original payloads should be backed up before production migration.
10. Module compatibility and persistence migration are evaluated separately.
