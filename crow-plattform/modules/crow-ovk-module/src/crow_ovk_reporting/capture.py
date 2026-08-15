from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from .models import InspectionTimeLedger, TimeAdjustment, TimeCategory, TimeSegment
from .service import ReportingRepository


def append_time_segment(
    repository: ReportingRepository,
    *,
    inspection_id: str,
    project_id: str,
    inspection_date: str,
    category: TimeCategory,
    started_at: str,
    ended_at: str,
    segment_id: str | None = None,
) -> InspectionTimeLedger:
    ledger = _load_or_create(repository, inspection_id, project_id, inspection_date)
    if ledger.project_id != project_id:
        raise ValueError("project_id does not match existing time ledger")
    if ledger.inspection_date != inspection_date:
        raise ValueError("inspection_date does not match existing time ledger")
    candidate = TimeSegment(
        segment_id=segment_id or f"segment-{uuid4()}",
        category=category,
        started_at=started_at,
        ended_at=ended_at,
    )
    if any(item.segment_id == candidate.segment_id for item in ledger.segments):
        return ledger
    _validate_segment(candidate)
    updated = InspectionTimeLedger(
        inspection_id=ledger.inspection_id,
        project_id=ledger.project_id,
        inspection_date=ledger.inspection_date,
        segments=(*ledger.segments, candidate),
        adjustments=ledger.adjustments,
    )
    repository.save_ledger(updated)
    return updated


def append_time_adjustment(
    repository: ReportingRepository,
    *,
    inspection_id: str,
    project_id: str,
    inspection_date: str,
    hours: Decimal,
    reason: str,
    changed_by: str,
    changed_at: str | None = None,
    adjustment_id: str | None = None,
) -> InspectionTimeLedger:
    ledger = _load_or_create(repository, inspection_id, project_id, inspection_date)
    if ledger.project_id != project_id:
        raise ValueError("project_id does not match existing time ledger")
    if ledger.inspection_date != inspection_date:
        raise ValueError("inspection_date does not match existing time ledger")
    if not reason.strip():
        raise ValueError("adjustment reason is required")
    if not changed_by.strip():
        raise ValueError("changed_by is required")
    candidate = TimeAdjustment(
        adjustment_id=adjustment_id or f"adjustment-{uuid4()}",
        hours=hours,
        reason=reason.strip(),
        changed_by=changed_by.strip(),
        changed_at=changed_at or datetime.now(UTC).isoformat(),
    )
    if any(item.adjustment_id == candidate.adjustment_id for item in ledger.adjustments):
        return ledger
    updated = InspectionTimeLedger(
        inspection_id=ledger.inspection_id,
        project_id=ledger.project_id,
        inspection_date=ledger.inspection_date,
        segments=ledger.segments,
        adjustments=(*ledger.adjustments, candidate),
    )
    repository.save_ledger(updated)
    return updated


def _load_or_create(
    repository: ReportingRepository,
    inspection_id: str,
    project_id: str,
    inspection_date: str,
) -> InspectionTimeLedger:
    try:
        return repository.load_ledger(inspection_id)
    except FileNotFoundError:
        return InspectionTimeLedger(
            inspection_id=inspection_id,
            project_id=project_id,
            inspection_date=inspection_date,
        )


def _validate_segment(segment: TimeSegment) -> None:
    start = datetime.fromisoformat(segment.started_at)
    end = datetime.fromisoformat(segment.ended_at)
    if end < start:
        raise ValueError("ended_at must not precede started_at")
