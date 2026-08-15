from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class ProductModuleStatus(StrEnum):
    ACTIVE = "active"
    PLANNED = "planned"


@dataclass(frozen=True, slots=True)
class ProductModule:
    id: str
    name: str
    status: ProductModuleStatus
    route: str
    api_prefixes: tuple[str, ...]
    data_dependencies: tuple[str, ...] = ()
    requires_modules: tuple[str, ...] = ()
    runtime_module_id: str | None = None

    def matches_api_path(self, path: str) -> bool:
        return any(path == prefix or path.startswith(f"{prefix}/") for prefix in self.api_prefixes)

    def matches_route_path(self, path: str) -> bool:
        return path == self.route or path.startswith(f"{self.route}/")


@dataclass(frozen=True, slots=True)
class ProductModuleCatalog:
    version: str
    modules: tuple[ProductModule, ...]

    def get(self, module_id: str) -> ProductModule:
        for module in self.modules:
            if module.id == module_id:
                return module
        raise KeyError(f"Unknown product module: {module_id}")

    def active_modules(self) -> tuple[ProductModule, ...]:
        return tuple(
            module for module in self.modules if module.status is ProductModuleStatus.ACTIVE
        )

    def module_for_api_path(self, path: str) -> ProductModule | None:
        matches = [module for module in self.modules if module.matches_api_path(path)]
        if not matches:
            return None
        return max(matches, key=lambda module: max(len(prefix) for prefix in module.api_prefixes))

    def module_for_route_path(self, path: str) -> ProductModule | None:
        matches = [module for module in self.modules if module.matches_route_path(path)]
        if not matches:
            return None
        return max(matches, key=lambda module: len(module.route))


@dataclass(frozen=True, slots=True)
class EntitlementEntry:
    module_id: str
    active: bool
    valid_until: date | None = None

    def is_active(self, *, today: date) -> bool:
        if not self.active:
            return False
        return self.valid_until is None or self.valid_until >= today


@dataclass(frozen=True, slots=True)
class CustomerEntitlements:
    customer_id: str
    entries: tuple[EntitlementEntry, ...]

    def has_active_module(self, module_id: str, *, today: date) -> bool:
        return any(
            entry.module_id == module_id and entry.is_active(today=today) for entry in self.entries
        )

    def active_module_ids(self, *, today: date) -> frozenset[str]:
        return frozenset(entry.module_id for entry in self.entries if entry.is_active(today=today))


@dataclass(frozen=True, slots=True)
class CustomerContext:
    customer_id: str
    user_id: str | None = None
    roles: tuple[str, ...] = ()
