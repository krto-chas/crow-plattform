from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class SourceRole(StrEnum):
    DRAWING = "drawing"
    MODEL = "model"
    SPECIFICATION = "specification"
    QUANTITY_REFERENCE = "quantity_reference"
    PROJECT_ARCHIVE = "project_archive"
    UNKNOWN = "unknown"


class ReferenceQuality(StrEnum):
    AUTHORITATIVE = "authoritative"
    PARTIAL = "partial"
    SUPPORTING = "supporting"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DatasetSource:
    source_id: str
    filename: str
    role: SourceRole
    reference_quality: ReferenceQuality
    size_bytes: int
    checksum_sha256: str
    media_type: str
    format_id: str
    format_version: str | None = None
    notes: tuple[str, ...] = ()
    external_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectDataset:
    dataset_id: str
    title: str
    schema_version: int = 1
    description: str = ""
    sources: tuple[DatasetSource, ...] = ()
    known_limitations: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "title": self.title,
            "description": self.description,
            "sources": [source.to_dict() for source in self.sources],
            "known_limitations": list(self.known_limitations),
            "metadata": self.metadata,
        }

    def validate(self) -> None:
        if not self.dataset_id.strip():
            raise ValueError("dataset_id must not be empty")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source_id values must be unique")
        checksums = [source.checksum_sha256 for source in self.sources]
        if any(len(checksum) != 64 for checksum in checksums):
            raise ValueError("all source checksums must be SHA-256 hex digests")


def relative_external_path(path: Path, base: Path | None) -> str:
    if base is None:
        return path.name
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return path.name
