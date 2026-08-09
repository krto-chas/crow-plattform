from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TightnessClass(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class ClaimOrigin(StrEnum):
    """Skiljer klartext i handling från härledd kunskap.

    STATED: står ordagrant i en projekthandling (citat + locator finns).
    INFERRED: härledd av Crow ur standard, branschpraxis eller regel.
    """

    STATED = "stated"
    INFERRED = "inferred"


@dataclass(frozen=True, slots=True)
class TextLocator:
    document_id: str
    line_number: int
    source_text: str


@dataclass(frozen=True, slots=True)
class TightnessRequirement:
    duct_family: str
    tightness_class: TightnessClass
    origin: ClaimOrigin
    locator: TextLocator


@dataclass(frozen=True, slots=True)
class TestScopeRequirement:
    target: str
    percentage: int
    origin: ClaimOrigin
    locator: TextLocator

    def __post_init__(self) -> None:
        if not 0 <= self.percentage <= 100:
            raise ValueError(f"percentage must be 0-100, got {self.percentage}")


@dataclass(frozen=True, slots=True)
class TightnessConflict:
    duct_family: str
    classes: tuple[TightnessClass, ...]
    requirements: tuple[TightnessRequirement, ...]

    @property
    def strictest_class(self) -> TightnessClass:
        order = {
            TightnessClass.A: 0,
            TightnessClass.B: 1,
            TightnessClass.C: 2,
            TightnessClass.D: 3,
        }
        return max(self.classes, key=lambda item: order[item])
