from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AdjustmentType(StrEnum):
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"


class AdjustmentKind(StrEnum):
    MARKUP = "markup"
    DISCOUNT = "discount"
    INDEX = "index"
    RISK = "risk"
    OTHER = "other"


class AdjustmentBase(StrEnum):
    NET_AMOUNT = "net_amount"
    RUNNING_TOTAL = "running_total"


@dataclass(frozen=True, slots=True)
class CommercialAdjustmentRule:
    id: str
    name: str
    kind: AdjustmentKind
    adjustment_type: AdjustmentType
    base: AdjustmentBase
    value: float
    categories: tuple[str, ...] = ()
    cost_types: tuple[str, ...] = ()
    enabled: bool = True
    priority: int = 0
    version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class CommercialAdjustmentProfile:
    id: str
    name: str
    version: str
    currency: str
    rules: tuple[CommercialAdjustmentRule, ...]


@dataclass(frozen=True, slots=True)
class AppliedAdjustment:
    id: str
    rule_id: str
    kind: AdjustmentKind
    description: str
    base_amount: float
    rate: float | None
    amount: float
    currency: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class AdjustedCommercialImpact:
    commercial_impact_id: str
    description: str
    category: str | None
    cost_type: str | None
    net_amount: float
    adjustments: tuple[AppliedAdjustment, ...]
    adjusted_total: float
    currency: str


@dataclass(frozen=True, slots=True)
class AdjustedCommercialImpactSet:
    project_id: str
    baseline_id: str
    source_price_book_id: str
    adjustment_profile_id: str
    currency: str
    impacts: tuple[AdjustedCommercialImpact, ...]
    unresolved_count: int

    @property
    def net_total(self) -> float:
        return sum(item.net_amount for item in self.impacts)

    @property
    def adjustment_total(self) -> float:
        return sum(adjustment.amount for item in self.impacts for adjustment in item.adjustments)

    @property
    def grand_total(self) -> float:
        return sum(item.adjusted_total for item in self.impacts)
