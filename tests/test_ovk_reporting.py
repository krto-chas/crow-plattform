from decimal import Decimal

from crow_ovk_reporting import (
    CertificationProfile,
    InspectionTimeLedger,
    TimeAdjustment,
    TimeCategory,
    TimeSegment,
    adjustment_hours,
    build_report_rows,
    calculated_hours,
    report_to_csv,
    reported_hours,
)


def _ledger(inspection_id: str, inspection_date: str) -> InspectionTimeLedger:
    return InspectionTimeLedger(
        inspection_id=inspection_id,
        project_id="project-1",
        inspection_date=inspection_date,
        segments=(
            TimeSegment(
                segment_id="field-1",
                category=TimeCategory.FIELD,
                started_at="2026-05-04T08:00:00+02:00",
                ended_at="2026-05-04T10:00:00+02:00",
            ),
            TimeSegment(
                segment_id="protocol-1",
                category=TimeCategory.PROTOCOL,
                started_at="2026-05-04T13:00:00+02:00",
                ended_at="2026-05-04T13:30:00+02:00",
            ),
        ),
        adjustments=(
            TimeAdjustment(
                adjustment_id="adj-1",
                hours=Decimal("0.50"),
                reason="Efterarbete som inte fångades automatiskt",
                changed_by="inspector",
                changed_at="2026-05-04T14:00:00+02:00",
            ),
        ),
    )


def test_reported_time_preserves_calculated_and_adjustment_values() -> None:
    ledger = _ledger("ovk-1", "2026-05-04")

    assert calculated_hours(ledger) == Decimal("2.50")
    assert adjustment_hours(ledger) == Decimal("0.50")
    assert reported_hours(ledger) == Decimal("3.00")


def test_reporting_period_is_not_assumed_to_be_calendar_year() -> None:
    profile = CertificationProfile(
        profile_id="kiwa-1",
        inspector_name="Inspector",
        certification_body="Kiwa",
        certificate_number="CERT-1",
        authorization="K",
        reporting_period_start="2026-04-18",
        reporting_period_end="2027-04-17",
    )
    rows = build_report_rows(
        profile,
        (
            _ledger("inside", "2026-05-04"),
            _ledger("outside", "2027-04-18"),
        ),
    )

    assert [row.inspection_id for row in rows] == ["inside"]


def test_csv_contains_traceable_hours_and_certification_metadata() -> None:
    profile = CertificationProfile(
        profile_id="generic-1",
        inspector_name="Inspector",
        certification_body="Generic",
        certificate_number="CERT-1",
        authorization="N",
        reporting_period_start="2026-01-01",
        reporting_period_end="2026-12-31",
    )
    rows = build_report_rows(profile, (_ledger("ovk-1", "2026-05-04"),))
    csv_text = report_to_csv(profile, rows)

    assert "CERT-1" in csv_text
    assert "ovk-1,project-1,2026-05-04,2.50,0.50,3.00" in csv_text
    assert "total_reported_hours,3.00" in csv_text
