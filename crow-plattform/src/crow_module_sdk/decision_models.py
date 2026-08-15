from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from .models import Claim, Evidence


class ReviewStatus(StrEnum):
    AUTOMATED = "automated"
    HUMAN_REVIEW = "human_review"
    CONFIRMED = "confirmed"


class CommercialTreatment(StrEnum):
    INFORMATION = "information"
    QUESTION = "question"
    RESERVATION = "reservation"
    EXCLUSION = "exclusion"
    PRICED_OPTION = "priced_option"
    SEPARATE_RISK_LINE = "separate_risk_line"


class OpportunityStatus(StrEnum):
    IDENTIFIED = "identified"
    REVIEW = "review"
    SUBMITTED = "submitted"
    RESERVED = "reserved"
    OPTION = "option"
    REJECTED = "rejected"
    CONFIRMED = "confirmed"


@dataclass(frozen=True, slots=True)
class Conflict:
    id: str
    conflict_key: tuple[str, str, str]
    claim_ids: tuple[str, ...]
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class AuthorityRule:
    id: str
    higher_document_id: str
    lower_document_id: str
    description: str


@dataclass(frozen=True, slots=True)
class AuthorityPolicy:
    id: str
    rules: tuple[AuthorityRule, ...]
    confirmed: bool = False


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    id: str
    conflict_id: str
    selected_claim_id: str | None
    rejected_claim_ids: tuple[str, ...]
    rule_id: str | None
    status: ReviewStatus
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class AcceptedClaim:
    id: str
    claim: Claim
    authority_decision_id: str


@dataclass(frozen=True, slots=True)
class TechnicalDelta:
    id: str
    subject: str
    property: str
    accepted_value: Decimal
    alternative_value: Decimal
    unit: str
    absolute_delta: Decimal
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class RoundingPolicy:
    quantum: Decimal = Decimal("0.01")
    rounding: str = ROUND_HALF_UP

    def apply(self, value: Decimal) -> Decimal:
        return value.quantize(self.quantum, rounding=self.rounding)


@dataclass(frozen=True, slots=True)
class CommercialImpact:
    id: str
    technical_delta_id: str
    base_amount: Decimal
    alternative_amount: Decimal
    delta_amount: Decimal
    currency: str
    pricing_trace_ids: tuple[str, ...]
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class AtaOpportunity:
    id: str
    commercial_impact_id: str
    treatment: CommercialTreatment
    status: OpportunityStatus
    title: str
    rationale: str


@dataclass(frozen=True, slots=True)
class EstimateLine:
    id: str
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    total: Decimal
    currency: str
    source_opportunity_id: str


@dataclass(frozen=True, slots=True)
class ClientQuestion:
    id: str
    subject: str
    body: str
    source_opportunity_id: str


@dataclass(frozen=True, slots=True)
class Reservation:
    id: str
    body: str
    source_opportunity_id: str
