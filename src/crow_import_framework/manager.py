from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

from .models import ImportedAsset, ImportSource
from .registry import ImportRegistry


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


class ImportManager:
    def __init__(self, registry: ImportRegistry, manifest_root: Path | None = None) -> None:
        self.registry = registry
        self.manifest_root = manifest_root

    def import_file(self, path: Path, media_type: str | None = None) -> ImportedAsset:
        source = ImportSource(path=path, filename=path.name, media_type=media_type)
        plugin = self.registry.resolve(source)
        asset = plugin.import_asset(source)
        if self.manifest_root:
            self.manifest_root.mkdir(parents=True, exist_ok=True)
            target = self.manifest_root / f"{asset.checksum_sha256}.json"
            target.write_text(
                json.dumps(_jsonable(asdict(asset)), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return asset
