from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from crow_ovk import OvkInspection


class ReviewStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class OvkReviewDecision:
    observation_id: str
    source_text: str
    evidence_ref: str
    reason: str
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer: str | None = None
    note: str = ""


@dataclass(frozen=True, slots=True)
class OvkWorkflowRecord:
    inspection: OvkInspection
    review: tuple[OvkReviewDecision, ...] = ()
    updated_at: str = ""

    @property
    def unresolved_review_count(self) -> int:
        return sum(item.status is ReviewStatus.PENDING for item in self.review)

    @property
    def protocol_ready(self) -> bool:
        return self.inspection.conclusion.value != "pending" and self.unresolved_review_count == 0
