from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from importlib.resources import files
from typing import Any

from .models import TightnessClass

_FLOW_QUANTUM = Decimal("0.000001")
_PRESSURE_EXPONENT = 0.65


@dataclass(frozen=True)
class StandardReference:
    standard_id: str
    title: str


class PressureTestKnowledge:
    """Läckagefaktorer, standarder och kanalfamiljstermer för täthetsprovning.

    Kunskapen paketeras som JSON med en enda källa: samma faktorer driver
    extraktion, kalkyl och framtida protokollgenerering.
    """

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = payload
        raw_classes = payload["tightness_classes"]
        self._factors: dict[TightnessClass, Decimal] = {
            TightnessClass(name): Decimal(str(entry["leakage_factor"]))
            for name, entry in raw_classes.items()
        }
        self._atc: dict[TightnessClass, str] = {
            TightnessClass(name): str(entry["atc"]) for name, entry in raw_classes.items()
        }
        self._duct_families: dict[str, tuple[str, ...]] = {
            family: tuple(str(term) for term in terms)
            for family, terms in payload["duct_families"].items()
        }

    @property
    def duct_families(self) -> Mapping[str, tuple[str, ...]]:
        return self._duct_families

    def leakage_factor(self, tightness_class: TightnessClass) -> Decimal:
        return self._factors[tightness_class]

    def atc_class(self, tightness_class: TightnessClass) -> str:
        return self._atc[tightness_class]

    def standards(self) -> tuple[StandardReference, ...]:
        return tuple(
            StandardReference(standard_id=str(entry["id"]), title=str(entry["title"]))
            for entry in self._payload["standards"]
        )

    def allowed_leakage_flow(
        self,
        tightness_class: TightnessClass,
        pressure_pa: int,
        duct_area_m2: Decimal,
    ) -> Decimal:
        """q_max = c * |p|^0,65 * A i l/s, kvantiserad till 6 decimaler.

        Exponenten beräknas i float (IEEE 754, deterministiskt för samma
        indata) och resultatet låses till Decimal enligt ADR-0009-andan.
        """
        if pressure_pa == 0:
            raise ValueError("pressure_pa must be non-zero")
        if duct_area_m2 <= 0:
            raise ValueError("duct_area_m2 must be positive")
        factor = self._factors[tightness_class]
        pressure_term = Decimal(str(abs(pressure_pa) ** _PRESSURE_EXPONENT))
        raw = factor * pressure_term * duct_area_m2
        return raw.quantize(_FLOW_QUANTUM, rounding=ROUND_HALF_UP)


def load_knowledge() -> PressureTestKnowledge:
    resource = files("crow_pressure_test").joinpath("tathetsprovning_lexikon.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("tathetsprovning_lexikon.json must contain a JSON object")
    return PressureTestKnowledge(payload)
