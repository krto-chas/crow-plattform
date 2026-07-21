from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EstimateLineStatus(StrEnum):
    READY = "ready"


@dataclass(frozen=True, slots=True)
class EstimateLineProvenance:
    commercial_impact_id: str
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
    adjustment_profile_id: str
    commercial_review_event_id: str
    adjustment_ids: tuple[str, ...]
    trace: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EstimateLine:
    id: str
    line_number: int
    status: EstimateLineStatus
    description: str
    cost_type: str | None
    quantity: float
    unit: str
    unit_rate: float
    net_amount: float
    adjustment_amount: float
    total_amount: float
    currency: str
    provenance: EstimateLineProvenance
    fingerprint: str


@dataclass(frozen=True, slots=True)
class Estimate:
    project_id: str
    baseline_id: str
    estimate_id: str
    currency: str
    price_book_id: str
    adjustment_profile_id: str
    commercial_review_event_id: str
    lines: tuple[EstimateLine, ...] = ()

    @property
    def net_total(self) -> float:
        return sum(line.net_amount for line in self.lines)

    @property
    def adjustment_total(self) -> float:
        return sum(line.adjustment_amount for line in self.lines)

    @property
    def grand_total(self) -> float:
        return sum(line.total_amount for line in self.lines)
