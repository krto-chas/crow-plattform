from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .versioning import Version

MigrationFunction = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class Migration:
    from_version: str
    to_version: str
    migrate: MigrationFunction


class MigrationRegistry:
    def __init__(self) -> None:
        self._migrations: dict[tuple[str, str], Migration] = {}

    def register(self, migration: Migration) -> None:
        source = Version.parse(migration.from_version)
        target = Version.parse(migration.to_version)
        if target <= source:
            raise ValueError("Migration target must be newer than source")
        key = (migration.from_version, migration.to_version)
        if key in self._migrations:
            raise ValueError(f"Migration already registered: {key}")
        self._migrations[key] = migration

    def migrate(
        self,
        payload: Mapping[str, object],
        *,
        current_version: str,
        target_version: str,
    ) -> dict[str, Any]:
        if current_version == target_version:
            return dict(payload)

        path = self._find_path(current_version, target_version)
        current = dict(payload)
        for migration in path:
            current = migration.migrate(current)
            current["schema_version"] = migration.to_version
        return current

    def _find_path(self, current_version: str, target_version: str) -> tuple[Migration, ...]:
        frontier: list[tuple[str, tuple[Migration, ...]]] = [(current_version, ())]
        visited: set[str] = set()

        while frontier:
            version, path = frontier.pop(0)
            if version in visited:
                continue
            visited.add(version)
            for (source, target), migration in sorted(self._migrations.items()):
                if source != version:
                    continue
                next_path = path + (migration,)
                if target == target_version:
                    return next_path
                frontier.append((target, next_path))

        raise ValueError(f"No migration path from {current_version} to {target_version}")
