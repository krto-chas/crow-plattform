"""Bygger bevakningslistan ur utfärdade intyg och öppna ombesiktningsärenden.

Bevakningen är en härledd vy utan eget lagrat tillstånd: per byggnad väljs det
senast utfärdade intyget deterministiskt, och öppna ombesiktningsärenden med
åtgärdsfrist bevakas separat. Varje post bär skriven basis — intygspostens basis
är intygets egen härledda frist-basis, så proveniensen följer med hela vägen.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from crow_ovk_intyg import IntygResult, OvkIntyg
from crow_ovk_workflow import CaseStatus, OvkReinspectionCase

from .models import SCHEMA_VERSION, WatchItem, WatchList, WatchSource, WatchStatus


def build_watchlist(
    *,
    project_id: str,
    intyg: tuple[OvkIntyg, ...],
    cases: tuple[OvkReinspectionCase, ...],
    today: date,
    reminder_window_days: int = 180,
) -> WatchList:
    items: list[WatchItem] = []
    for current in _latest_intyg_per_building(intyg):
        items.append(_intyg_item(current, today=today, reminder_window_days=reminder_window_days))
    for case in cases:
        if case.status is CaseStatus.CLOSED or case.deadline is None:
            continue
        items.append(_case_item(case, today=today, reminder_window_days=reminder_window_days))
    return WatchList(
        project_id=project_id,
        generated_at=today,
        reminder_window_days=reminder_window_days,
        items=tuple(sorted(items, key=_sort_key)),
    )


def _latest_intyg_per_building(intyg: tuple[OvkIntyg, ...]) -> tuple[OvkIntyg, ...]:
    latest: dict[str, OvkIntyg] = {}
    for current in sorted(intyg, key=lambda item: (item.issued_date, item.intyg_id)):
        latest[current.building_id] = current
    return tuple(latest[key] for key in sorted(latest))


def _intyg_item(
    intyg: OvkIntyg,
    *,
    today: date,
    reminder_window_days: int,
) -> WatchItem:
    if intyg.result is IntygResult.EJ_GODKAND:
        return WatchItem(
            project_id=intyg.project_id,
            building_id=intyg.building_id,
            object_name=intyg.object_name,
            source=WatchSource.INTYG,
            ref_id=intyg.intyg_id,
            inspection_id=intyg.inspection_id,
            status=WatchStatus.OMBESIKTNING_KRAVS,
            basis=intyg.next_inspection.basis,
        )
    due_date = intyg.next_inspection.due_date
    if due_date is None:
        return WatchItem(
            project_id=intyg.project_id,
            building_id=intyg.building_id,
            object_name=intyg.object_name,
            source=WatchSource.INTYG,
            ref_id=intyg.intyg_id,
            inspection_id=intyg.inspection_id,
            status=WatchStatus.INGEN_FRIST,
            basis=intyg.next_inspection.basis,
        )
    return WatchItem(
        project_id=intyg.project_id,
        building_id=intyg.building_id,
        object_name=intyg.object_name,
        source=WatchSource.INTYG,
        ref_id=intyg.intyg_id,
        inspection_id=intyg.inspection_id,
        status=_deadline_status(due_date, today=today, window_days=reminder_window_days),
        basis=intyg.next_inspection.basis,
        due_date=due_date,
        interval_years=intyg.next_inspection.interval_years,
        days_until=(due_date - today).days,
    )


def _case_item(
    case: OvkReinspectionCase,
    *,
    today: date,
    reminder_window_days: int,
) -> WatchItem:
    deadline = case.deadline
    assert deadline is not None
    return WatchItem(
        project_id=case.project_id,
        building_id=case.building_id,
        object_name=case.source_inspection_id,
        source=WatchSource.OMBESIKTNING,
        ref_id=case.case_id,
        inspection_id=case.source_inspection_id,
        status=_deadline_status(deadline, today=today, window_days=reminder_window_days),
        basis=(
            f"Åtgärdsfrist {deadline.isoformat()} för öppet ombesiktningsärende "
            f"{case.case_id} (källbesiktning {case.source_inspection_id})."
        ),
        due_date=deadline,
        days_until=(deadline - today).days,
    )


def _deadline_status(due_date: date, *, today: date, window_days: int) -> WatchStatus:
    if due_date < today:
        return WatchStatus.FORSENAD
    if (due_date - today).days <= window_days:
        return WatchStatus.PAMINNELSE
    return WatchStatus.OK


_STATUS_ORDER = {
    WatchStatus.FORSENAD: 0,
    WatchStatus.OMBESIKTNING_KRAVS: 1,
    WatchStatus.PAMINNELSE: 2,
    WatchStatus.OK: 3,
    WatchStatus.INGEN_FRIST: 4,
}


def _sort_key(item: WatchItem) -> tuple[int, date, str]:
    return (
        _STATUS_ORDER[item.status],
        item.due_date or date.max,
        item.building_id,
    )


def watchlist_to_payload(watchlist: WatchList) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": watchlist.project_id,
        "generated_at": watchlist.generated_at.isoformat(),
        "reminder_window_days": watchlist.reminder_window_days,
        "overdue_count": watchlist.overdue_count,
        "reminder_count": watchlist.reminder_count,
        "items": [
            {
                "project_id": item.project_id,
                "building_id": item.building_id,
                "object_name": item.object_name,
                "source": item.source.value,
                "ref_id": item.ref_id,
                "inspection_id": item.inspection_id,
                "status": item.status.value,
                "basis": item.basis,
                "due_date": item.due_date.isoformat() if item.due_date is not None else None,
                "interval_years": item.interval_years,
                "days_until": item.days_until,
            }
            for item in watchlist.items
        ],
    }
