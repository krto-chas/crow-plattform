from pathlib import Path

from crow_commercial_adjustment import (
    AdjustedCommercialImpactSet,
    load_adjusted,
    load_profile,
    save_adjusted,
    summarize_adjustments,
    write_profile_template,
)


def test_profile_template_loads(tmp_path: Path) -> None:
    path = tmp_path / "adjustments.json"
    write_profile_template(path)

    profile = load_profile(path)

    assert profile.id == "crow.adjustments.example"
    assert len(profile.rules) == 2


def test_adjusted_result_round_trip(tmp_path: Path) -> None:
    result = AdjustedCommercialImpactSet(
        project_id="project",
        baseline_id="baseline",
        source_price_book_id="book",
        adjustment_profile_id="profile",
        currency="SEK",
        impacts=(),
        unresolved_count=0,
    )
    path = tmp_path / "adjusted.json"

    save_adjusted(result, path)

    assert load_adjusted(path) == result


def test_empty_summary() -> None:
    summary = summarize_adjustments(
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

    assert summary["net_total"] == 0.0
    assert summary["adjustment_total"] == 0.0
    assert summary["grand_total"] == 0.0
