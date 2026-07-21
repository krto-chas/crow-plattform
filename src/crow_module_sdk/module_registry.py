from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points

from .plugin import CrowModulePlugin

ENTRYPOINT_GROUP = "crow.modules"


class DuplicateModuleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RegisteredModule:
    module_id: str
    version: str
    plugin: CrowModulePlugin
    origin: str


class ModuleRegistry:
    def __init__(self) -> None:
        self._modules: dict[str, RegisteredModule] = {}

    def register(self, plugin: CrowModulePlugin, *, origin: str = "manual") -> RegisteredModule:
        manifest = plugin.manifest()
        if manifest.module_id in self._modules:
            existing = self._modules[manifest.module_id]
            raise DuplicateModuleError(
                f"Module {manifest.module_id} is already registered from {existing.origin}"
            )
        registered = RegisteredModule(
            module_id=manifest.module_id,
            version=manifest.version,
            plugin=plugin,
            origin=origin,
        )
        self._modules[manifest.module_id] = registered
        return registered

    def get(self, module_id: str) -> RegisteredModule:
        try:
            return self._modules[module_id]
        except KeyError as error:
            raise KeyError(f"Unknown Crow module: {module_id}") from error

    def list(self) -> tuple[RegisteredModule, ...]:
        return tuple(sorted(self._modules.values(), key=lambda item: item.module_id))

    def discover(
        self, candidates: Iterable[EntryPoint] | None = None
    ) -> tuple[RegisteredModule, ...]:
        discovered = (
            tuple(entry_points(group=ENTRYPOINT_GROUP)) if candidates is None else tuple(candidates)
        )
        result: list[RegisteredModule] = []
        for candidate in sorted(discovered, key=lambda item: item.name):
            loaded = candidate.load()
            plugin = loaded() if isinstance(loaded, type) else loaded
            result.append(self.register(plugin, origin=f"entrypoint:{candidate.name}"))
        return tuple(result)
