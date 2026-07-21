from __future__ import annotations

from dataclasses import dataclass, field

from .models import ImportSource
from .plugin import ImportPlugin


@dataclass
class ImportRegistry:
    _plugins: list[ImportPlugin] = field(default_factory=list)

    def register(self, plugin: ImportPlugin) -> None:
        if any(item.id == plugin.id for item in self._plugins):
            raise ValueError(f"Importer already registered: {plugin.id}")
        self._plugins.append(plugin)
        self._plugins.sort(key=lambda item: item.priority)

    def plugins(self) -> tuple[ImportPlugin, ...]:
        return tuple(self._plugins)

    def resolve(self, source: ImportSource) -> ImportPlugin:
        with source.path.open("rb") as handle:
            header = handle.read(4096)
        for plugin in self._plugins:
            if plugin.supports(source, header):
                return plugin
        raise ValueError(f"Unsupported file format: {source.filename}")
