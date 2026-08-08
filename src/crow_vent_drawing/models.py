from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class DrawingRef:
    """Tolkat ritningsnummer, t.ex. V-57-1-41103 → plan 11, del 03."""

    number: str
    series: str
    plan: str
    part: str


@dataclass(frozen=True, slots=True)
class ApartmentRecord:
    apartment_id: str
    stairwell_id: str
    plan: str
    rok: int | None
    area_m2: Decimal | None
    area_is_authoritative: bool
    source_document: str


@dataclass(frozen=True, slots=True)
class LevelObservation:
    elevation_m: Decimal
    source_document: str


@dataclass(frozen=True, slots=True)
class DrawingTextAssessment:
    document_id: str
    extraction_status: str
    apartment_label_count: int
    level_label_count: int
    needs_raster_review: bool
    notes: tuple[str, ...] = ()
