from __future__ import annotations

from abc import ABC, abstractmethod

from .models import ImportedAsset, ImportSource


class ImportPlugin(ABC):
    id: str
    format_id: str
    extensions: tuple[str, ...]
    media_types: tuple[str, ...] = ()
    priority: int = 100

    def supports(self, source: ImportSource, header: bytes) -> bool:
        suffix = source.path.suffix.lower()
        return suffix in self.extensions or self.sniff(source, header)

    def sniff(self, source: ImportSource, header: bytes) -> bool:
        return False

    @abstractmethod
    def import_asset(self, source: ImportSource) -> ImportedAsset:
        raise NotImplementedError
