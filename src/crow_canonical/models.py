from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CanonicalObjectType(StrEnum):
    AIR_HANDLING_UNIT = "air_handling_unit"
    FAN = "fan"
    DUCT = "duct"
    DAMPER = "damper"
    SILENCER = "silencer"
    AIR_TERMINAL = "air_terminal"
    HEAT_EXCHANGER = "heat_exchanger"
    AIR_TREATMENT_COMPONENT = "air_treatment_component"
    ACCESSORY = "accessory"


@dataclass(frozen=True)
class CanonicalEvidence:
    source_id: str
    source_kind: str
    locator: str | None
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalObject:
    canonical_id: str
    object_type: CanonicalObjectType
    discipline: str
    name: str
    confidence: float
    properties: dict[str, Any]
    evidence: CanonicalEvidence
    status: str = "interpreted"
    review_reasons: tuple[str, ...] = ()
