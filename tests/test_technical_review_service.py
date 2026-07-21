from datetime import UTC, datetime
from pathlib import Path

from crow_technical_review import (
    ReviewStatus,
    ReviewTargetType,
    TechnicalReviewSet,
    load_review_set,
    save_review_set,
    summarize_reviews,
    transition_record,
)
from crow_technical_review.models import ReviewRecord


def test_review_set_round_trip(tmp_path: Path) -> None:
    original = TechnicalReviewSet(
        project_id="project",
        records=(
            ReviewRecord(
                target_id="decision:1",
                target_type=ReviewTargetType.TECHNICAL_DECISION,
                status=ReviewStatus.PROPOSED,
                latest_event_id=None,
            ),
        ),
    )
    updated = transition_record(
        original,
        "decision:1",
        ReviewStatus.APPROVED,
        "reviewer",
        "Technically verified.",
        datetime(2026, 7, 19, tzinfo=UTC),
    )
    path = tmp_path / "reviews.json"

    save_review_set(updated, path)

    assert load_review_set(path) == updated


def test_review_summary() -> None:
    review_set = TechnicalReviewSet(
        project_id="project",
        records=(
            ReviewRecord(
                target_id="decision:1",
                target_type=ReviewTargetType.TECHNICAL_DECISION,
                status=ReviewStatus.APPROVED,
                latest_event_id="event:1",
            ),
            ReviewRecord(
                target_id="validation:1",
                target_type=ReviewTargetType.VALIDATION_ISSUE,
                status=ReviewStatus.NEEDS_INFORMATION,
                latest_event_id="event:2",
            ),
        ),
    )

    summary = summarize_reviews(review_set)

    assert summary["records"] == 2
    assert summary["by_status"]["approved"] == 1
    assert summary["by_status"]["needs_information"] == 1
