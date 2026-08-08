from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from math import pi
from typing import Any, Mapping

from crow_riser_model.models import RiserString

_AREA_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class PressureTestCandidate:
    candidate_id: str
    stairwell_id: str
    apartment_id: str
    kind: str
    dimension: str
    length_m: Decimal
    duct_area_m2: Decimal
    source: str
    evidence: Mapping[str, Any]


def circular_duct_area(dimension: str, length_m: Decimal) -> Decimal:
    if length_m <= 0:
        raise ValueError("length_m must be positive")
    diameter_mm = _diameter_mm(dimension)
    diameter_m = Decimal(diameter_mm) / Decimal("1000")
    circumference = Decimal(str(pi)) * diameter_m
    return (circumference * length_m).quantize(_AREA_QUANTUM, rounding=ROUND_HALF_UP)


def candidate_from_riser_string(item: RiserString) -> PressureTestCandidate:
    area = circular_duct_area(item.dimension, item.length_m)
    candidate_id = ":".join(
        (item.stairwell_id, item.apartment_id, item.kind, item.dimension, str(item.length_m))
    )
    return PressureTestCandidate(
        candidate_id=candidate_id,
        stairwell_id=item.stairwell_id,
        apartment_id=item.apartment_id,
        kind=item.kind,
        dimension=item.dimension,
        length_m=item.length_m,
        duct_area_m2=area,
        source="riser_model",
        evidence=item.evidence,
    )


def candidate_to_payload(candidate: PressureTestCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "stairwell_id": candidate.stairwell_id,
        "apartment_id": candidate.apartment_id,
        "kind": candidate.kind,
        "dimension": candidate.dimension,
        "length_m": str(candidate.length_m),
        "duct_area_m2": str(candidate.duct_area_m2),
        "source": candidate.source,
        "evidence": dict(candidate.evidence),
    }


def _diameter_mm(dimension: str) -> str:
    normalized = dimension.strip().upper().replace("Ø", "").replace("⌀", "")
    if normalized.startswith("DN"):
        normalized = normalized[2:]
    normalized = normalized.strip()
    if not normalized.isdigit() or int(normalized) <= 0:
        raise ValueError(f"unsupported circular duct dimension: {dimension!r}")
    return normalized
