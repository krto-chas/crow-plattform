"""Multi-source material takeoff consolidation.

Extracts material quantity lines (delmängder) from heterogeneous project
sources — CAD geometry takeoffs, spreadsheet quantity schedules, and
specification text — normalises them through the vent lexicon, and
reconciles them into one consolidated bill of quantities where every line
knows which sources support it and where sources disagree.

Domain-neutral by design: the line key is (kind, code, dimension), so
future VS and el modules can reuse the consolidation unchanged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

SCHEMA_VERSION = "crow-takeoff-consolidation-v0.1"


class LineKind(StrEnum):
    DUCT = "duct"
    COMPONENT = "component"


class SourceKind(StrEnum):
    GEOMETRY = "geometry"
    TABLE = "table"
    TEXT = "text"


class LineStatus(StrEnum):
    SINGLE_SOURCE = "single_source"
    CORROBORATED = "corroborated"
    DISCREPANT = "discrepant"
    UNIT_MISMATCH = "unit_mismatch"


@dataclass(frozen=True)
class SourceLine:
    """One material quantity claim from one source."""

    source_id: str
    source_kind: SourceKind
    kind: LineKind
    code: str
    label: str
    dimension: str
    quantity: float
    unit: str
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def line_key(self) -> tuple[str, str, str]:
        return (self.kind.value, self.code, self.dimension)


@dataclass(frozen=True)
class SourceTakeoff:
    source_id: str
    source_kind: SourceKind
    lines: tuple[SourceLine, ...]
    skipped: tuple[dict[str, Any], ...] = ()


def line_id(key: tuple[str, str, str]) -> str:
    digest = hashlib.sha256("|".join(key).encode("utf-8")).hexdigest()
    return f"takeoff-line:{digest[:16]}"


def dimension_text(
    shape: str, diameter_mm: int | None, width_mm: int | None, height_mm: int | None
) -> str:
    if shape == "circular" and diameter_mm is not None:
        return f"Ø{diameter_mm}"
    if shape == "rectangular" and width_mm is not None and height_mm is not None:
        return f"{width_mm}x{height_mm}"
    return "Ej angiven"
