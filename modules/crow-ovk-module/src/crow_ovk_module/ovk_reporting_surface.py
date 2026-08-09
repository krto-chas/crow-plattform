from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from crow_ovk_reporting import (
    CertificationProfile,
    ReportingRepository,
    build_report_rows,
    calculated_hours,
    ledger_from_payload,
    report_to_csv,
    reported_hours,
)
from fastapi import APIRouter, HTTPException, Response


def ovk_reporting_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    repository = ReportingRepository(data_root)

    @router.put("/api/ovk/reporting/time/{inspection_id}", response_model=None)
    def save_time(inspection_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            ledger = ledger_from_payload({**payload, "inspection_id": inspection_id})
            repository.save_ledger(ledger)
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_TIME_LEDGER"},
            ) from exc
        return {
            "inspection_id": ledger.inspection_id,
            "calculated_hours": str(calculated_hours(ledger)),
            "reported_hours": str(reported_hours(ledger)),
        }

    @router.get("/api/ovk/reporting/time/{inspection_id}", response_model=None)
    def get_time(inspection_id: str) -> dict[str, Any]:
        try:
            ledger = repository.load_ledger(inspection_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "TIME_LEDGER_NOT_FOUND"},
            ) from exc
        return {
            "inspection_id": ledger.inspection_id,
            "project_id": ledger.project_id,
            "inspection_date": ledger.inspection_date,
            "calculated_hours": str(calculated_hours(ledger)),
            "reported_hours": str(reported_hours(ledger)),
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

    @router.put("/api/ovk/reporting/certification/{profile_id}", response_model=None)
    def save_profile(profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            profile = CertificationProfile(
                profile_id=profile_id,
                inspector_name=str(payload["inspector_name"]),
                certification_body=str(payload["certification_body"]),
                certificate_number=str(payload["certificate_number"]),
                authorization=str(payload["authorization"]),
                reporting_period_start=str(payload["reporting_period_start"]),
                reporting_period_end=str(payload["reporting_period_end"]),
            )
            repository.save_profile(profile)
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_CERTIFICATION_PROFILE"},
            ) from exc
        return {"profile_id": profile.profile_id, "saved": True}

    @router.get("/api/ovk/reporting/annual/{profile_id}", response_model=None)
    def annual_report(profile_id: str) -> dict[str, Any]:
        try:
            profile = repository.load_profile(profile_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "CERTIFICATION_PROFILE_NOT_FOUND"},
            ) from exc
        rows = build_report_rows(profile, repository.list_ledgers())
        total = sum((item.reported_hours for item in rows), Decimal("0"))
        return {
            "profile_id": profile.profile_id,
            "certification_body": profile.certification_body,
            "period_start": profile.reporting_period_start,
            "period_end": profile.reporting_period_end,
            "total_hours": str(total),
            "inspections": [
                {
                    "inspection_id": item.inspection_id,
                    "project_id": item.project_id,
                    "inspection_date": item.inspection_date,
                    "calculated_hours": str(item.calculated_hours),
                    "adjustment_hours": str(item.adjustment_hours),
                    "reported_hours": str(item.reported_hours),
                }
                for item in rows
            ],
        }

    @router.get("/api/ovk/reporting/annual/{profile_id}.csv", response_class=Response)
    def annual_report_csv(profile_id: str) -> Response:
        try:
            profile = repository.load_profile(profile_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "CERTIFICATION_PROFILE_NOT_FOUND"},
            ) from exc
        rows = build_report_rows(profile, repository.list_ledgers())
        return Response(
            content=report_to_csv(profile, rows),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="ovk-annual-{profile_id}.csv"'},
        )

    return router
