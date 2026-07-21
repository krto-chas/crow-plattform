import pytest

from crow_module_conformance import Migration, MigrationRegistry


def test_migration_registry_executes_complete_path() -> None:
    registry = MigrationRegistry()
    registry.register(
        Migration(
            "1.0.0",
            "1.1.0",
            lambda payload: {**payload, "authority": "explicit"},
        )
    )
    registry.register(
        Migration(
            "1.1.0",
            "2.0.0",
            lambda payload: {**payload, "audit_enabled": True},
        )
    )

    migrated = registry.migrate(
        {"schema_version": "1.0.0"},
        current_version="1.0.0",
        target_version="2.0.0",
    )

    assert migrated["schema_version"] == "2.0.0"
    assert migrated["authority"] == "explicit"
    assert migrated["audit_enabled"] is True


def test_missing_migration_path_is_rejected() -> None:
    registry = MigrationRegistry()

    with pytest.raises(ValueError, match="No migration path"):
        registry.migrate(
            {"schema_version": "1.0.0"},
            current_version="1.0.0",
            target_version="2.0.0",
        )
