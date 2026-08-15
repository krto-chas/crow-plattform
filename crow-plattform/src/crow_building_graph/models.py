from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class EvidenceKind(StrEnum):
    DWG = "dwg"
    DXF = "dxf"
    IFC = "ifc"
    PDF = "pdf"
    TEXT = "text"
    MANUAL = "manual"
    AI = "ai"
    SYSTEM = "system"


@dataclass(frozen=True)
class CrowEvidence:
    id: str
    kind: EvidenceKind
    source_id: str
    locator: str | None = None
    checksum: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class CrowProperty:
    id: str
    owner_id: str
    name: str
    value: Any
    unit: str | None = None
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 1.0
    revision: int = 1
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class CrowObject:
    id: str
    object_type: str
    discipline: str = "generic"
    name: str | None = None
    status: str = "active"
    evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    revision: int = 1
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class CrowRelation:
    id: str
    source_id: str
    relation_type: str
    target_id: str
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    revision: int = 1
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class CrowHistory:
    id: str
    entity_id: str
    entity_kind: str
    action: str
    revision: int
    snapshot: dict[str, Any]
    actor: str = "system"
    created_at: str = field(default_factory=utc_now)
