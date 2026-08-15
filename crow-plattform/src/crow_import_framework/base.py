from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any

from .models import ImportCapability, ImportedAsset, ImportSource, NormalizedObservation
from .plugin import ImportPlugin


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BasePlugin(ImportPlugin):
    capabilities: tuple[ImportCapability, ...] = (ImportCapability.METADATA,)

    def build(
        self,
        source: ImportSource,
        *,
        metadata: dict[str, Any] | None = None,
        structure: list[dict[str, Any]] | None = None,
        observations: list[NormalizedObservation] | None = None,
        preview: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
    ) -> ImportedAsset:
        media_type = (
            source.media_type
            or mimetypes.guess_type(source.filename)[0]
            or "application/octet-stream"
        )
        return ImportedAsset(
            importer_id=self.id,
            format_id=self.format_id,
            filename=source.filename,
            media_type=media_type,
            size_bytes=source.path.stat().st_size,
            checksum_sha256=sha256(source.path),
            capabilities=self.capabilities,
            metadata=metadata or {},
            structure=structure or [],
            observations=observations or [],
            preview=preview or {},
            warnings=warnings or [],
        )
