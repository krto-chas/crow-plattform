from pathlib import Path

from crow_technical_validation import (
    TechnicalValidationResult,
    load_profile,
    load_result,
    save_result,
    summarize_validation,
    write_profile_template,
)


def test_profile_template_loads(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    write_profile_template(path)

    profile = load_profile(path)

    assert profile.id == "crow.validation.ventilation.example"
    assert len(profile.requirements) == 2


def test_result_round_trip(tmp_path: Path) -> None:
    result = TechnicalValidationResult(
        project_id="project",
        profile_id="profile",
        checked_requirements=2,
    )
    path = tmp_path / "result.json"

    save_result(result, path)

    assert load_result(path) == result


def test_empty_summary() -> None:
    summary = summarize_validation(
        TechnicalValidationResult(
            project_id="project",
            profile_id="profile",
            checked_requirements=2,
        )
    )

    assert summary["issues"] == 0
    assert summary["blocking"] == 0
