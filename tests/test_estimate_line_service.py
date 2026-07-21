from pathlib import Path

from crow_estimate_line import (
    Estimate,
    load_estimate,
    save_estimate,
    summarize_estimate,
)


def test_estimate_round_trip(tmp_path: Path) -> None:
    estimate = Estimate(
        project_id="project",
        baseline_id="baseline",
        estimate_id="estimate:1",
        currency="SEK",
        price_book_id="book",
        adjustment_profile_id="profile",
        commercial_review_event_id="review-event:1",
    )
    path = tmp_path / "estimate.json"

    save_estimate(estimate, path)

    assert load_estimate(path) == estimate


def test_empty_estimate_summary() -> None:
    summary = summarize_estimate(
        Estimate(
            project_id="project",
            baseline_id="baseline",
            estimate_id="estimate:1",
            currency="SEK",
            price_book_id="book",
            adjustment_profile_id="profile",
            commercial_review_event_id="review-event:1",
        )
    )

    assert summary["lines"] == 0
    assert summary["net_total"] == 0.0
    assert summary["adjustment_total"] == 0.0
    assert summary["grand_total"] == 0.0
