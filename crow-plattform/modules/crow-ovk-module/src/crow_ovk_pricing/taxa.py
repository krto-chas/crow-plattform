"""OVK-taxa: à-priser, grundavgift, minimidebitering och intervallregler."""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from importlib.resources import files
from typing import Any

from .models import BuildingCategory, InspectionType, PricingBasis, VentilationSystemType

_FT_FTX = frozenset({VentilationSystemType.FT, VentilationSystemType.FTX})


class OvkTaxa:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = payload
        self._currency = str(payload["currency"])
        self._base_fee = Decimal(str(payload["base_fee"]))
        self._minimum_total = Decimal(str(payload["minimum_total"]))
        if self._base_fee < 0:
            raise ValueError("base_fee must be non-negative")
        if self._minimum_total < 0:
            raise ValueError("minimum_total must be non-negative")
        self._categories: dict[BuildingCategory, Mapping[str, Any]] = {
            BuildingCategory(name): entry for name, entry in payload["categories"].items()
        }
        intervals = payload["recurring_intervals"]
        self._school_or_care_years = int(intervals["school_or_care_years"])
        self._ft_ftx_years = int(intervals["ft_ftx_years"])
        self._s_f_fx_years = int(intervals["s_f_fx_years"])

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def base_fee(self) -> Decimal:
        return self._base_fee

    @property
    def minimum_total(self) -> Decimal:
        return self._minimum_total

    def basis(self, category: BuildingCategory) -> PricingBasis:
        return PricingBasis(str(self._category(category)["basis"]))

    def unit(self, category: BuildingCategory) -> str:
        return str(self._category(category)["unit"])

    def label(self, category: BuildingCategory) -> str:
        return str(self._category(category)["label"])

    def rate(
        self,
        category: BuildingCategory,
        inspection_type: InspectionType,
        system_type: VentilationSystemType | None = None,
    ) -> Decimal:
        entry = self._category(category)
        if self.basis(category) is PricingBasis.PER_AREA:
            if system_type is None:
                raise ValueError(f"system_type is required to price category {category.value!r}")
            rates_per_system = entry["rates_per_system"]
            system_rates = rates_per_system.get(system_type.value)
            if system_rates is None:
                raise ValueError(
                    f"no rate for system type {system_type.value!r} in category {category.value!r}"
                )
            raw = system_rates.get(inspection_type.value)
        else:
            raw = entry["rates"].get(inspection_type.value)
        if raw is None:
            raise ValueError(
                f"no rate for inspection type {inspection_type.value!r} "
                f"in category {category.value!r}"
            )
        rate = Decimal(str(raw))
        if rate <= 0:
            raise ValueError(
                f"rate must be positive for {category.value!r}/{inspection_type.value!r}"
            )
        return rate

    def recurring_interval_years(
        self,
        category: BuildingCategory,
        system_type: VentilationSystemType | None,
        *,
        school_or_care: bool = False,
    ) -> int | None:
        if category is BuildingCategory.SMAHUS:
            return None
        if school_or_care:
            return self._school_or_care_years
        if system_type is None:
            return None
        if system_type in _FT_FTX:
            return self._ft_ftx_years
        return self._s_f_fx_years

    def _category(self, category: BuildingCategory) -> Mapping[str, Any]:
        entry = self._categories.get(category)
        if entry is None:
            raise ValueError(f"category {category.value!r} is missing from the taxa lexicon")
        return entry


def load_taxa() -> OvkTaxa:
    resource = files("crow_ovk_pricing").joinpath("ovk_taxa_lexikon.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    return OvkTaxa(payload)
