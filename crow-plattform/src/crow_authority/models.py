from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class DocumentAuthorityType(StrEnum):
    CONTRACT = "contract"
    AB04_CHANGES = "ab04_changes"
    AB04 = "ab04"
    ORDER = "order"
    TENDER = "tender"
    MEASUREMENT_RULES = "measurement_rules"
    PRICED_BILL = "priced_bill"
    PRE_TENDER_SUPPLEMENT = "pre_tender_supplement"
    ADMINISTRATIVE_SPECIFICATIONS = "administrative_specifications"
    UNPRICED_BILL = "unpriced_bill"
    TECHNICAL_DESCRIPTION = "technical_description"
    DRAWING = "drawing"
    OTHER = "other"
    UNKNOWN = "unknown"


DEFAULT_AB04_HIERARCHY: tuple[DocumentAuthorityType, ...] = (
    DocumentAuthorityType.CONTRACT,
    DocumentAuthorityType.AB04_CHANGES,
    DocumentAuthorityType.AB04,
    DocumentAuthorityType.ORDER,
    DocumentAuthorityType.TENDER,
    DocumentAuthorityType.MEASUREMENT_RULES,
    DocumentAuthorityType.PRICED_BILL,
    DocumentAuthorityType.PRE_TENDER_SUPPLEMENT,
    DocumentAuthorityType.ADMINISTRATIVE_SPECIFICATIONS,
    DocumentAuthorityType.UNPRICED_BILL,
    DocumentAuthorityType.TECHNICAL_DESCRIPTION,
    DocumentAuthorityType.DRAWING,
    DocumentAuthorityType.OTHER,
    DocumentAuthorityType.UNKNOWN,
)


@dataclass(frozen=True, slots=True)
class DocumentAuthorityMetadata:
    document_id: str
    authority_type: DocumentAuthorityType
    title: str = ""
    issue_date: date | None = None
    revision: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorityFramework:
    id: str
    name: str
    hierarchy: tuple[DocumentAuthorityType, ...]
    source: str
    project_override: bool = False


class AuthorityDecisionStatus(StrEnum):
    ACCEPTED_CONSISTENT = "accepted_consistent"
    ACCEPTED_COMPLEMENTARY = "accepted_complementary"
    RESOLVED_BY_HIERARCHY = "resolved_by_hierarchy"
    RESOLVED_BY_DATE = "resolved_by_date"
    UNRESOLVED_MISSING_METADATA = "unresolved_missing_metadata"
    UNRESOLVED_TIE = "unresolved_tie"


@dataclass(frozen=True, slots=True)
class EvaluatedVariant:
    normalized_value: str
    unit: str | None
    candidate_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    best_rank: int | None
    latest_date: date | None


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    id: str
    cluster_id: str
    status: AuthorityDecisionStatus
    accepted_value: str | None
    accepted_unit: str | None
    accepted_candidate_ids: tuple[str, ...]
    accepted_document_ids: tuple[str, ...]
    evaluated_variants: tuple[EvaluatedVariant, ...]
    applied_rule: str
    explanation: str
    framework_id: str
    trace: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AuthorityResolution:
    project_id: str
    framework: AuthorityFramework
    decisions: tuple[AuthorityDecision, ...] = ()

    @property
    def resolved_count(self) -> int:
        return sum(
            decision.status
            in {
                AuthorityDecisionStatus.ACCEPTED_CONSISTENT,
                AuthorityDecisionStatus.ACCEPTED_COMPLEMENTARY,
                AuthorityDecisionStatus.RESOLVED_BY_HIERARCHY,
                AuthorityDecisionStatus.RESOLVED_BY_DATE,
            }
            for decision in self.decisions
        )

    @property
    def unresolved_count(self) -> int:
        return len(self.decisions) - self.resolved_count
