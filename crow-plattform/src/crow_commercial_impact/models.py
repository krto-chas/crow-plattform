from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CostType(StrEnum):
    LABOUR = "labour"
    MATERIAL = "material"
    EQUIPMENT = "equipment"
    SUBCONTRACT = "subcontract"
    OTHER = "other"


class PricingStatus(StrEnum):
    PRICED = "priced"
    MISSING_QUANTITY = "missing_quantity"
    MISSING_UNIT_RATE = "missing_unit_rate"
    REVIEW_REQUIRED = "review_required"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class UnitRate:
    id: str
    category: str
    property_name: str | None
    impact_types: tuple[str, ...]
    cost_type: CostType
    unit: str
    currency: str
    unit_rate: float
    description: str
    enabled: bool = True
    priority: int = 0
    version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class PriceBook:
    id: str
    name: str
    version: str
    currency: str
    rates: tuple[UnitRate, ...]


@dataclass(frozen=True, slots=True)
class CommercialImpactProvenance:
    scope_impact_id: str
    technical_delta_id: str
    decision_id: str | None
    review_event_id: str | None
    accepted_claim_ids: tuple[str, ...]
    authority_decision_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    scope_rule_id: str | None
    price_book_id: str
    unit_rate_id: str | None
    trace: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CommercialImpact:
    id: str
    scope_impact_id: str
    cost_type: CostType | None
    description: str
    quantity: float | None
    unit: str | None
    unit_rate: float | None
    currency: str
    amount: float | None
    pricing_status: PricingStatus
    requires_review: bool
    confidence: float | None
    provenance: CommercialImpactProvenance
    fingerprint: str


@dataclass(frozen=True, slots=True)
class CommercialImpactSet:
    project_id: str
    baseline_id: str
    price_book_id: str
    currency: str
    impacts: tuple[CommercialImpact, ...] = ()

    @property
    def priced_total(self) -> float:
        return sum(impact.amount or 0.0 for impact in self.impacts)

    @property
    def unresolved_count(self) -> int:
        return sum(
            impact.pricing_status not in {PricingStatus.PRICED, PricingStatus.NOT_APPLICABLE}
            for impact in self.impacts
        )
