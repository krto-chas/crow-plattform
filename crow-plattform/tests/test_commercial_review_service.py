from pathlib import Path

from crow_commercial_adjustment import AdjustedCommercialImpactSet
from crow_commercial_review import (
    initialize_commercial_review,
    load_review,
    save_review,
    summarize_review,
)


def test_review_round_trip(tmp_path: Path) -> None:
    review = initialize_commercial_review(
        AdjustedCommercialImpactSet(
            project_id="project",
            baseline_id="baseline",
            source_price_book_id="book",
            adjustment_profile_id="profile",
            currency="SEK",
            impacts=(),
            unresolved_count=0,
        )
    )
    path = tmp_path / "review.json"

    save_review(review, path)

    assert load_review(path) == review


def test_review_summary() -> None:
    review = initialize_commercial_review(
        AdjustedCommercialImpactSet(
            project_id="project",
            baseline_id="baseline",
            source_price_book_id="book",
            adjustment_profile_id="profile",
            currency="SEK",
            impacts=(),
            unresolved_count=0,
        )
    )

    summary = summarize_review(review)

    assert summary["status"] == "proposed"
    assert summary["approved"] is False
    assert summary["events"] == 0
