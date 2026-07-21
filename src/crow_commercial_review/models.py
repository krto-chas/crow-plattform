from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CommercialReviewStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_INFORMATION = "needs_information"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class CommercialReviewEvent:
    id: str
    previous_status: CommercialReviewStatus
    new_status: CommercialReviewStatus
    reviewer: str
    reason: str
    created_at: datetime
    supersedes_event_id: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class CommercialReview:
    project_id: str
    baseline_id: str
    adjustment_profile_id: str
    source_price_book_id: str
    currency: str
    grand_total: float
    unresolved_count: int
    status: CommercialReviewStatus
    latest_event_id: str | None = None
    history: tuple[CommercialReviewEvent, ...] = ()

    @property
    def is_approved(self) -> bool:
        return self.status == CommercialReviewStatus.APPROVED
