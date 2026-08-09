from decimal import Decimal

from crow_ovk_reporting import (
    ReportingRepository,
    TimeCategory,
    append_time_adjustment,
    append_time_segment,
    calculated_hours,
    reported_hours,
)


def test_append_segment_is_idempotent_and_preserves_category(tmp_path) -> None:
    repository = ReportingRepository(tmp_path)
    first = append_time_segment(
        repository,
        inspection_id="ovk-1",
        project_id="project-1",
        inspection_date="2026-08-09",
        category=TimeCategory.FIELD,
        started_at="2026-08-09T08:00:00+00:00",
        ended_at="2026-08-09T10:30:00+00:00",
        segment_id="field-fixed",
    )
    second = append_time_segment(
        repository,
        inspection_id="ovk-1",
        project_id="project-1",
        inspection_date="2026-08-09",
        category=TimeCategory.FIELD,
        started_at="2026-08-09T08:00:00+00:00",
        ended_at="2026-08-09T10:30:00+00:00",
        segment_id="field-fixed",
    )

    assert len(first.segments) == 1
    assert len(second.segments) == 1
    assert second.segments[0].category is TimeCategory.FIELD
    assert calculated_hours(second) == Decimal("2.50")


def test_adjustment_is_separate_from_calculated_time(tmp_path) -> None:
    repository = ReportingRepository(tmp_path)
    append_time_segment(
        repository,
        inspection_id="ovk-2",
        project_id="project-1",
        inspection_date="2026-08-09",
        category=TimeCategory.REVIEW,
        started_at="2026-08-09T10:00:00+00:00",
        ended_at="2026-08-09T11:00:00+00:00",
        segment_id="review-1",
    )
    ledger = append_time_adjustment(
        repository,
        inspection_id="ovk-2",
        project_id="project-1",
        inspection_date="2026-08-09",
        hours=Decimal("0.50"),
        reason="Efterarbete utanför timer",
        changed_by="Inspector",
        changed_at="2026-08-09T11:05:00+00:00",
        adjustment_id="adjustment-1",
    )

    assert calculated_hours(ledger) == Decimal("1.00")
    assert reported_hours(ledger) == Decimal("1.50")
    assert ledger.adjustments[0].reason == "Efterarbete utanför timer"


def test_existing_ledger_rejects_project_mismatch(tmp_path) -> None:
    repository = ReportingRepository(tmp_path)
    append_time_segment(
        repository,
        inspection_id="ovk-3",
        project_id="project-1",
        inspection_date="2026-08-09",
        category=TimeCategory.PROTOCOL,
        started_at="2026-08-09T10:00:00+00:00",
        ended_at="2026-08-09T10:15:00+00:00",
    )

    try:
        append_time_segment(
            repository,
            inspection_id="ovk-3",
            project_id="project-2",
            inspection_date="2026-08-09",
            category=TimeCategory.PROTOCOL,
            started_at="2026-08-09T10:20:00+00:00",
            ended_at="2026-08-09T10:30:00+00:00",
        )
    except ValueError as exc:
        assert "project_id" in str(exc)
    else:
        raise AssertionError("project mismatch must be rejected")
