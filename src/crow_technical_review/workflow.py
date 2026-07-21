from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from crow_decision_engine import DecisionEvaluationResult
from crow_technical_validation import TechnicalValidationResult, ValidationSeverity

from .models import (
    ReviewEvent,
    ReviewRecord,
    ReviewStatus,
    ReviewTargetType,
    TechnicalReviewSet,
)

_ALLOWED_TRANSITIONS: dict[ReviewStatus, tuple[ReviewStatus, ...]] = {
    ReviewStatus.PROPOSED: (
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
        ReviewStatus.NEEDS_INFORMATION,
        ReviewStatus.SUPERSEDED,
    ),
    ReviewStatus.NEEDS_INFORMATION: (
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
        ReviewStatus.SUPERSEDED,
    ),
    ReviewStatus.APPROVED: (ReviewStatus.SUPERSEDED,),
    ReviewStatus.REJECTED: (ReviewStatus.SUPERSEDED,),
    ReviewStatus.SUPERSEDED: (),
}


def initialize_review_set(
    decisions: DecisionEvaluationResult,
    validation: TechnicalValidationResult,
) -> TechnicalReviewSet:
    if decisions.project_id != validation.project_id:
        raise ValueError("Decision and validation project IDs must match")

    records = [
        ReviewRecord(
            target_id=candidate.id,
            target_type=ReviewTargetType.TECHNICAL_DECISION,
            status=ReviewStatus.PROPOSED,
            latest_event_id=None,
        )
        for candidate in decisions.candidates
    ]
    records.extend(
        ReviewRecord(
            target_id=issue.id,
            target_type=ReviewTargetType.VALIDATION_ISSUE,
            status=ReviewStatus.PROPOSED,
            latest_event_id=None,
        )
        for issue in validation.issues
    )
    return TechnicalReviewSet(
        project_id=decisions.project_id,
        records=tuple(sorted(records, key=lambda item: (item.target_type.value, item.target_id))),
    )


def _fingerprint(
    record: ReviewRecord,
    new_status: ReviewStatus,
    reviewer: str,
    reason: str,
    created_at: datetime,
) -> str:
    material = "|".join(
        (
            record.target_id,
            record.target_type.value,
            record.status.value,
            new_status.value,
            reviewer,
            reason,
            created_at.isoformat(),
            record.latest_event_id or "",
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def transition_record(
    review_set: TechnicalReviewSet,
    target_id: str,
    new_status: ReviewStatus,
    reviewer: str,
    reason: str,
    created_at: datetime | None = None,
) -> TechnicalReviewSet:
    if not reviewer.strip():
        raise ValueError("Reviewer is required")
    if not reason.strip():
        raise ValueError("Reason is required")

    timestamp = created_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("Review timestamps must be timezone-aware")

    updated: list[ReviewRecord] = []
    found = False
    for record in review_set.records:
        if record.target_id != target_id:
            updated.append(record)
            continue
        found = True
        if new_status not in _ALLOWED_TRANSITIONS[record.status]:
            raise ValueError(
                f"Invalid review transition: {record.status.value} -> {new_status.value}"
            )
        fingerprint = _fingerprint(record, new_status, reviewer, reason, timestamp)
        event = ReviewEvent(
            id=f"review-event:{fingerprint}",
            target_id=record.target_id,
            target_type=record.target_type,
            previous_status=record.status,
            new_status=new_status,
            reviewer=reviewer.strip(),
            reason=reason.strip(),
            created_at=timestamp,
            supersedes_event_id=record.latest_event_id,
            fingerprint=fingerprint,
        )
        updated.append(
            ReviewRecord(
                target_id=record.target_id,
                target_type=record.target_type,
                status=new_status,
                latest_event_id=event.id,
                history=(*record.history, event),
            )
        )

    if not found:
        raise KeyError(f"Unknown review target: {target_id}")

    return TechnicalReviewSet(
        project_id=review_set.project_id,
        records=tuple(sorted(updated, key=lambda item: (item.target_type.value, item.target_id))),
    )


def can_approve_decision(
    review_set: TechnicalReviewSet,
    validation: TechnicalValidationResult,
) -> bool:
    blocking_ids = {
        issue.id for issue in validation.issues if issue.severity == ValidationSeverity.BLOCKING
    }
    unresolved = {
        record.target_id
        for record in review_set.records
        if record.target_id in blocking_ids
        and record.status not in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}
    }
    return not unresolved
