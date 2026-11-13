from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from crow_ovk import OvkInspection

from .coverage import CoverageError, InspectionCoverage, validate_coverage_for_finalization


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
class InspectionPlanning:
    inspector_id: str
    planned_date: date
    inspection_type: str

    def __post_init__(self) -> None:
        if not self.inspector_id.strip():
            raise ValueError("inspector_id is required")
        if self.inspection_type not in ("forstagang", "aterkommande"):
            raise ValueError("invalid inspection_type")


@dataclass(frozen=True, slots=True)
class OvkWorkflowRecord:
    inspection: OvkInspection
    review: tuple[OvkReviewDecision, ...] = ()
    updated_at: str = ""
    coverage: InspectionCoverage | None = None
    planning: InspectionPlanning | None = None

    @property
    def unresolved_review_count(self) -> int:
        return sum(item.status is ReviewStatus.PENDING for item in self.review)

    @property
    def coverage_complete(self) -> bool:
        """Alla fläktar/aggregat explicit adresserade (pass 101-grinden)."""
        try:
            validate_coverage_for_finalization(self.coverage)
        except CoverageError:
            return False
        return True

    @property
    def protocol_ready(self) -> bool:
        return (
            self.inspection.conclusion.value != "pending"
            and self.unresolved_review_count == 0
            and self.coverage_complete
        )
