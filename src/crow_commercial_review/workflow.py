from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime

from crow_commercial_adjustment import AdjustedCommercialImpactSet

from .models import (
    CommercialReview,
    CommercialReviewEvent,
    CommercialReviewStatus,
)

_ALLOWED: dict[CommercialReviewStatus, set[CommercialReviewStatus]] = {
    CommercialReviewStatus.PROPOSED: {
        CommercialReviewStatus.APPROVED,
        CommercialReviewStatus.REJECTED,
        CommercialReviewStatus.NEEDS_INFORMATION,
        CommercialReviewStatus.SUPERSEDED,
    },
    CommercialReviewStatus.NEEDS_INFORMATION: {
        CommercialReviewStatus.APPROVED,
        CommercialReviewStatus.REJECTED,
        CommercialReviewStatus.SUPERSEDED,
    },
    CommercialReviewStatus.APPROVED: {
        CommercialReviewStatus.SUPERSEDED,
    },
    CommercialReviewStatus.REJECTED: {
        CommercialReviewStatus.SUPERSEDED,
    },
    CommercialReviewStatus.SUPERSEDED: set(),
}


def initialize_commercial_review(
    adjusted: AdjustedCommercialImpactSet,
) -> CommercialReview:
    return CommercialReview(
        project_id=adjusted.project_id,
        baseline_id=adjusted.baseline_id,
        adjustment_profile_id=adjusted.adjustment_profile_id,
        source_price_book_id=adjusted.source_price_book_id,
        currency=adjusted.currency,
        grand_total=adjusted.grand_total,
        unresolved_count=adjusted.unresolved_count,
        status=CommercialReviewStatus.PROPOSED,
    )


def can_approve(review: CommercialReview) -> bool:
    return review.unresolved_count == 0


def transition_commercial_review(
    review: CommercialReview,
    new_status: CommercialReviewStatus,
    reviewer: str,
    reason: str,
    created_at: datetime,
) -> CommercialReview:
    reviewer = reviewer.strip()
    reason = reason.strip()
    if not reviewer:
        raise ValueError("Reviewer is required")
    if not reason:
        raise ValueError("Reason is required")
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("Review timestamp must be timezone-aware")
    if new_status not in _ALLOWED[review.status]:
        raise ValueError(
            f"Invalid commercial review transition: {review.status.value} -> {new_status.value}"
        )
    if new_status == CommercialReviewStatus.APPROVED and not can_approve(review):
        raise ValueError("Commercial review cannot be approved while items are unresolved")

    material = "|".join(
        (
            review.project_id,
            review.adjustment_profile_id,
            review.status.value,
            new_status.value,
            reviewer,
            reason,
            created_at.isoformat(),
            review.latest_event_id or "",
        )
    )
    fingerprint = hashlib.sha256(material.encode("utf-8")).hexdigest()
    event = CommercialReviewEvent(
        id=f"commercial-review-event:{fingerprint}",
        previous_status=review.status,
        new_status=new_status,
        reviewer=reviewer,
        reason=reason,
        created_at=created_at,
        supersedes_event_id=review.latest_event_id,
        fingerprint=fingerprint,
    )
    return replace(
        review,
        status=new_status,
        latest_event_id=event.id,
        history=review.history + (event,),
    )
