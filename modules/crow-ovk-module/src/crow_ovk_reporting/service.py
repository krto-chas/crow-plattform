from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any

from .models import (
    AnnualReportRow,
    CertificationProfile,
    InspectionTimeLedger,
    TimeAdjustment,
    TimeCategory,
    TimeSegment,
)

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_HOURS = Decimal("3600")


def calculated_hours(ledger: InspectionTimeLedger) -> Decimal:
    seconds = sum((_duration_seconds(item) for item in ledger.segments), Decimal("0"))
    return (seconds / _HOURS).quantize(Decimal("0.01"))


def adjustment_hours(ledger: InspectionTimeLedger) -> Decimal:
    return sum((item.hours for item in ledger.adjustments), Decimal("0")).quantize(
        Decimal("0.01")
    )


def reported_hours(ledger: InspectionTimeLedger) -> Decimal:
    total = calculated_hours(ledger) + adjustment_hours(ledger)
    return max(total, Decimal("0.00")).quantize(Decimal("0.01"))


def build_report_rows(
    profile: CertificationProfile,
    ledgers: tuple[InspectionTimeLedger, ...],
) -> tuple[AnnualReportRow, ...]:
    rows: list[AnnualReportRow] = []
    for ledger in ledgers:
        if profile.reporting_period_start <= ledger.inspection_date <= profile.reporting_period_end:
            rows.append(
                AnnualReportRow(
                    inspection_id=ledger.inspection_id,
                    project_id=ledger.project_id,
                    inspection_date=ledger.inspection_date,
                    calculated_hours=calculated_hours(ledger),
                    adjustment_hours=adjustment_hours(ledger),
                    reported_hours=reported_hours(ledger),
                )
            )
    return tuple(sorted(rows, key=lambda item: (item.inspection_date, item.inspection_id)))


def report_to_csv(profile: CertificationProfile, rows: tuple[AnnualReportRow, ...]) -> str:
    target = StringIO()
    writer = csv.writer(target, lineterminator="\n")
    writer.writerow(["certification_body", profile.certification_body])
    writer.writerow(["certificate_number", profile.certificate_number])
    writer.writerow(["inspector_name", profile.inspector_name])
    writer.writerow(["authorization", profile.authorization])
    writer.writerow(["period_start", profile.reporting_period_start])
    writer.writerow(["period_end", profile.reporting_period_end])
    writer.writerow([])
    writer.writerow(
        [
            "inspection_id",
            "project_id",
            "inspection_date",
            "calculated_hours",
            "adjustment_hours",
            "reported_hours",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.inspection_id,
                row.project_id,
                row.inspection_date,
                str(row.calculated_hours),
                str(row.adjustment_hours),
                str(row.reported_hours),
            ]
        )
    total = sum((row.reported_hours for row in rows), Decimal("0"))
    writer.writerow([])
    writer.writerow(["total_reported_hours", str(total)])
    return target.getvalue()


class ReportingRepository:
    def __init__(self, data_root: Path) -> None:
        self._ledger_root = data_root / "ovk-time-ledger"
        self._profile_root = data_root / "ovk-certification-profile"

    def save_ledger(self, ledger: InspectionTimeLedger) -> None:
        _validate_id(ledger.inspection_id)
        self._ledger_root.mkdir(parents=True, exist_ok=True)
        _atomic_write(
            self._ledger_root / f"{ledger.inspection_id}.json",
            _ledger_payload(ledger),
        )

    def load_ledger(self, inspection_id: str) -> InspectionTimeLedger:
        _validate_id(inspection_id)
        target = self._ledger_root / f"{inspection_id}.json"
        return _ledger_from_payload(_read_object(target))

    def list_ledgers(self) -> tuple[InspectionTimeLedger, ...]:
        if not self._ledger_root.exists():
            return ()
        return tuple(
            _ledger_from_payload(_read_object(path))
            for path in sorted(self._ledger_root.glob("*.json"))
        )

    def save_profile(self, profile: CertificationProfile) -> None:
        _validate_id(profile.profile_id)
        self._profile_root.mkdir(parents=True, exist_ok=True)
        _atomic_write(
            self._profile_root / f"{profile.profile_id}.json",
            {
                "profile_id": profile.profile_id,
                "inspector_name": profile.inspector_name,
                "certification_body": profile.certification_body,
                "certificate_number": profile.certificate_number,
                "authorization": profile.authorization,
                "reporting_period_start": profile.reporting_period_start,
                "reporting_period_end": profile.reporting_period_end,
            },
        )

    def load_profile(self, profile_id: str) -> CertificationProfile:
        _validate_id(profile_id)
        item = _read_object(self._profile_root / f"{profile_id}.json")
        return CertificationProfile(
            profile_id=str(item["profile_id"]),
            inspector_name=str(item["inspector_name"]),
            certification_body=str(item["certification_body"]),
            certificate_number=str(item["certificate_number"]),
            authorization=str(item["authorization"]),
            reporting_period_start=str(item["reporting_period_start"]),
            reporting_period_end=str(item["reporting_period_end"]),
        )


def ledger_from_payload(payload: dict[str, Any]) -> InspectionTimeLedger:
    return _ledger_from_payload(payload)


def _duration_seconds(segment: TimeSegment) -> Decimal:
    start = datetime.fromisoformat(segment.started_at)
    end = datetime.fromisoformat(segment.ended_at)
    if end < start:
        raise ValueError("ended_at must not precede started_at")
    return Decimal(str((end - start).total_seconds()))


def _ledger_payload(ledger: InspectionTimeLedger) -> dict[str, Any]:
    return {
        "inspection_id": ledger.inspection_id,
        "project_id": ledger.project_id,
        "inspection_date": ledger.inspection_date,
        "segments": [
            {
                "segment_id": item.segment_id,
                "category": item.category.value,
                "started_at": item.started_at,
                "ended_at": item.ended_at,
            }
            for item in ledger.segments
        ],
        "adjustments": [
            {
                "adjustment_id": item.adjustment_id,
                "hours": str(item.hours),
                "reason": item.reason,
                "changed_by": item.changed_by,
                "changed_at": item.changed_at,
            }
            for item in ledger.adjustments
        ],
    }


def _ledger_from_payload(payload: dict[str, Any]) -> InspectionTimeLedger:
    segments = tuple(
        TimeSegment(
            segment_id=str(item["segment_id"]),
            category=TimeCategory(str(item["category"])),
            started_at=str(item["started_at"]),
            ended_at=str(item["ended_at"]),
        )
        for item in _object_list(payload.get("segments"))
    )
    adjustments = tuple(
        TimeAdjustment(
            adjustment_id=str(item["adjustment_id"]),
            hours=Decimal(str(item["hours"])),
            reason=str(item["reason"]),
            changed_by=str(item["changed_by"]),
            changed_at=str(item["changed_at"]),
        )
        for item in _object_list(payload.get("adjustments"))
    )
    return InspectionTimeLedger(
        inspection_id=str(payload["inspection_id"]),
        project_id=str(payload["project_id"]),
        inspection_date=str(payload["inspection_date"]),
        segments=segments,
        adjustments=adjustments,
    )


def _object_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _read_object(path: Path) -> dict[str, Any]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object in {path.name}")
    return payload


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(canonical, encoding="utf-8")
    temporary.replace(path)


def _validate_id(value: str) -> None:
    if not _SAFE_ID.fullmatch(value):
        raise ValueError("invalid identifier")
