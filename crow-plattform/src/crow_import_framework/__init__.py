from .manager import ImportManager
from .models import (
    ImportCapability,
    ImportedAsset,
    ImportSource,
    NormalizedLocator,
    NormalizedObservation,
)
from .plugin import ImportPlugin
from .plugins import DEFAULT_PLUGINS
from .registry import ImportRegistry


def create_default_registry() -> ImportRegistry:
    registry = ImportRegistry()
    for plugin_type in DEFAULT_PLUGINS:
        registry.register(plugin_type())
    return registry


__all__ = [
    "DEFAULT_PLUGINS",
    "ImportCapability",
    "ImportedAsset",
    "ImportManager",
    "ImportPlugin",
    "ImportRegistry",
    "ImportSource",
    "NormalizedLocator",
    "NormalizedObservation",
    "create_default_registry",
]
