from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ImportCapability(StrEnum):
    METADATA = "metadata"
    TEXT = "text"
    STRUCTURE = "structure"
    PREVIEW = "preview"
    GEOMETRY_2D = "geometry_2d"
    GEOMETRY_3D = "geometry_3d"


@dataclass(frozen=True)
class ImportSource:
    path: Path
    filename: str
    media_type: str | None = None


@dataclass(frozen=True)
class NormalizedLocator:
    kind: str
    value: dict[str, Any]


@dataclass(frozen=True)
class NormalizedObservation:
    observation_type: str
    value: Any
    locator: NormalizedLocator
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportedAsset:
    importer_id: str
    format_id: str
    filename: str
    media_type: str
    size_bytes: int
    checksum_sha256: str
    capabilities: tuple[ImportCapability, ...]
    metadata: dict[str, Any]
    structure: list[dict[str, Any]]
    observations: list[NormalizedObservation]
    preview: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
