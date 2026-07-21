from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ScopeImpactType(StrEnum):
    ADDED_WORK = "added_work"
    OMITTED_WORK = "omitted_work"
    CHANGED_WORK = "changed_work"
    NO_SCOPE_CHANGE = "no_scope_change"
    REVIEW_REQUIRED = "review_required"


class QuantityBasis(StrEnum):
    DELTA_QUANTITY = "delta_quantity"
    APPROVED_QUANTITY = "approved_quantity"
    BASELINE_QUANTITY = "baseline_quantity"
    FIXED = "fixed"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ScopeImpactRule:
    id: str
    name: str
    categories: tuple[str, ...]
    property_names: tuple[str, ...]
    change_directions: tuple[str, ...]
    impact_type: ScopeImpactType
    quantity_basis: QuantityBasis
    output_unit: str | None
    multiplier: float = 1.0
    fixed_quantity: float | None = None
    description_template: str = "{title}"
    enabled: bool = True
    priority: int = 0
    version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class ScopeImpactRuleSet:
    id: str
    name: str
    version: str
    rules: tuple[ScopeImpactRule, ...]


@dataclass(frozen=True, slots=True)
class ScopeImpactProvenance:
    technical_delta_id: str
    baseline_item_id: str | None
    decision_id: str | None
    review_event_id: str | None
    accepted_claim_ids: tuple[str, ...]
    authority_decision_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    rule_id: str | None
    rule_set_id: str
    trace: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScopeImpact:
    id: str
    impact_type: ScopeImpactType
    category: str
    object_ref: str | None
    property_name: str | None
    description: str
    quantity: float | None
    unit: str | None
    confidence: float | None
    requires_review: bool
    provenance: ScopeImpactProvenance
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ScopeImpactSet:
    project_id: str
    baseline_id: str
    rule_set_id: str
    impacts: tuple[ScopeImpact, ...] = ()

    @property
    def review_required_count(self) -> int:
        return sum(impact.requires_review for impact in self.impacts)
