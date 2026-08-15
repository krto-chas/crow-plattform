from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReviewStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_INFORMATION = "needs_information"
    SUPERSEDED = "superseded"


class ReviewTargetType(StrEnum):
    TECHNICAL_DECISION = "technical_decision"
    VALIDATION_ISSUE = "validation_issue"


@dataclass(frozen=True, slots=True)
class ReviewEvent:
    id: str
    target_id: str
    target_type: ReviewTargetType
    previous_status: ReviewStatus
    new_status: ReviewStatus
    reviewer: str
    reason: str
    created_at: datetime
    supersedes_event_id: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    target_id: str
    target_type: ReviewTargetType
    status: ReviewStatus
    latest_event_id: str | None
    history: tuple[ReviewEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class TechnicalReviewSet:
    project_id: str
    records: tuple[ReviewRecord, ...] = ()

    @property
    def approved_count(self) -> int:
        return sum(record.status == ReviewStatus.APPROVED for record in self.records)
