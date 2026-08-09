from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol


class ApartmentLike(Protocol):
    """Strukturellt kontrakt mot ritningsextraktionen (t.ex. crow_vent_drawing)."""

    @property
    def apartment_id(self) -> str: ...

    @property
    def stairwell_id(self) -> str: ...

    @property
    def plan(self) -> str: ...


@dataclass(frozen=True)
class RiserConfiguration:
    """Systemkonfiguration för vertikala strängar från lägenhet till toppanslutning.

    Generell per betjäningsområde: ett FTX-system på vind får top_plan = vindsplan,
    ett radhus med eget aggregat får sitt eget top_plan. String_kinds speglar
    flödesschemat (Berghällen: tilluft, frånluft, imkanal per lgh).
    """

    top_plan: str
    string_kinds: tuple[str, ...] = ("tilluft", "franluft", "imkanal")
    attic_allowance_m: Decimal = Decimal("1.0")
    default_dimension: str = "Ø160"
    dimension_by_kind: Mapping[str, str] = field(default_factory=dict)
    medium_code_by_kind: Mapping[str, str] = field(
        default_factory=lambda: {"tilluft": "T1", "franluft": "F1", "imkanal": "IM1"}
    )

    def dimension_for(self, kind: str) -> str:
        return self.dimension_by_kind.get(kind, self.default_dimension)

    def medium_code_for(self, kind: str) -> str:
        return self.medium_code_by_kind.get(kind, kind.upper())


class LevelTable:
    """Plushöjder per plan; höjdskillnad ger stränglängd."""

    def __init__(self, elevations: Mapping[str, Decimal]) -> None:
        self._elevations = dict(elevations)

    @classmethod
    def from_pairs(cls, pairs: Mapping[str, str | float | Decimal]) -> LevelTable:
        return cls({plan: Decimal(str(value)) for plan, value in pairs.items()})

    def elevation(self, plan: str) -> Decimal | None:
        return self._elevations.get(plan)

    def height_to(self, plan: str, top_plan: str) -> Decimal | None:
        low = self.elevation(plan)
        high = self.elevation(top_plan)
        if low is None or high is None or high <= low:
            return None
        return high - low


@dataclass(frozen=True)
class RiserString:
    apartment_id: str
    stairwell_id: str
    kind: str
    plan: str
    dimension: str
    length_m: Decimal
    evidence: Mapping[str, Any]


@dataclass(frozen=True)
class StairwellSummary:
    stairwell_id: str
    apartment_count: int
    string_count: int
    total_length_m: Decimal


@dataclass(frozen=True)
class RiserModelResult:
    strings: tuple[RiserString, ...]
    summaries: tuple[StairwellSummary, ...]
    skipped: tuple[Mapping[str, Any], ...] = ()

    @property
    def string_count(self) -> int:
        return len(self.strings)

    @property
    def total_length_m(self) -> Decimal:
        return sum((item.length_m for item in self.strings), Decimal("0"))
