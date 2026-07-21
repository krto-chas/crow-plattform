from datetime import UTC, datetime

import pytest

from crow_commercial_adjustment import AdjustedCommercialImpactSet
from crow_commercial_review import (
    CommercialReviewStatus,
    can_approve,
    initialize_commercial_review,
    transition_commercial_review,
)


def adjusted(unresolved: int = 0) -> AdjustedCommercialImpactSet:
    return AdjustedCommercialImpactSet(
        project_id="project",
        baseline_id="baseline",
        source_price_book_id="book",
        adjustment_profile_id="profile",
        currency="SEK",
        impacts=(),
        unresolved_count=unresolved,
    )


def test_initialization() -> None:
    review = initialize_commercial_review(adjusted())

    assert review.status == CommercialReviewStatus.PROPOSED
    assert review.project_id == "project"
    assert review.history == ()


def test_approval_creates_immutable_event() -> None:
    review = initialize_commercial_review(adjusted())
    updated = transition_commercial_review(
        review,
        CommercialReviewStatus.APPROVED,
        "Reviewer",
        "Commercial basis verified.",
        datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
    )

    assert review.status == CommercialReviewStatus.PROPOSED
    assert updated.status == CommercialReviewStatus.APPROVED
    assert len(updated.history) == 1
    assert updated.latest_event_id == updated.history[0].id


def test_unresolved_items_block_approval() -> None:
    review = initialize_commercial_review(adjusted(unresolved=1))

    assert not can_approve(review)
    with pytest.raises(ValueError):
        transition_commercial_review(
            review,
            CommercialReviewStatus.APPROVED,
            "Reviewer",
            "Approve.",
            datetime.now(UTC),
        )


def test_invalid_transition_is_rejected() -> None:
    review = initialize_commercial_review(adjusted())
    approved = transition_commercial_review(
        review,
        CommercialReviewStatus.APPROVED,
        "Reviewer",
        "Approved.",
        datetime.now(UTC),
    )

    with pytest.raises(ValueError):
        transition_commercial_review(
            approved,
            CommercialReviewStatus.REJECTED,
            "Reviewer",
            "Changed mind.",
            datetime.now(UTC),
        )


def test_reviewer_reason_and_timezone_are_required() -> None:
    review = initialize_commercial_review(adjusted())

    with pytest.raises(ValueError):
        transition_commercial_review(
            review,
            CommercialReviewStatus.NEEDS_INFORMATION,
            "",
            "Missing.",
            datetime.now(UTC),
        )
    with pytest.raises(ValueError):
        transition_commercial_review(
            review,
            CommercialReviewStatus.NEEDS_INFORMATION,
            "Reviewer",
            "",
            datetime.now(UTC),
        )
    with pytest.raises(ValueError):
        transition_commercial_review(
            review,
            CommercialReviewStatus.NEEDS_INFORMATION,
            "Reviewer",
            "Missing.",
            datetime(2026, 7, 19, 12, 0),
        )
