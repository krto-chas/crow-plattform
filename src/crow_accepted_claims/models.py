from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AcceptanceBasis(StrEnum):
    COMPLEMENTARY = "complementary"
    CONSENSUS = "consensus"
    AUTHORITY_HIERARCHY = "authority_hierarchy"
    LATEST_DATE = "latest_date"


@dataclass(frozen=True, slots=True)
class AcceptedClaimProvenance:
    cluster_id: str
    authority_decision_id: str
    candidate_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    framework_id: str
    applied_rule: str
    trace: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AcceptedClaim:
    id: str
    semantic_key: str
    subject: str
    predicate: str
    value: str
    unit: str | None
    confidence: float
    acceptance_basis: AcceptanceBasis
    provenance: AcceptedClaimProvenance
    fingerprint: str


@dataclass(frozen=True, slots=True)
class PendingClaim:
    cluster_id: str
    authority_decision_id: str
    reason: str
    status: str


@dataclass(frozen=True, slots=True)
class AcceptedClaimSet:
    project_id: str
    claims: tuple[AcceptedClaim, ...] = ()
    pending: tuple[PendingClaim, ...] = ()

    @property
    def accepted_count(self) -> int:
        return len(self.claims)

    @property
    def pending_count(self) -> int:
        return len(self.pending)
