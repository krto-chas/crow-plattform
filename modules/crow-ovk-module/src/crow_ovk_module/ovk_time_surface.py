from __future__ import annotations

from decimal import Decimal, InvalidOperation
from importlib import resources
from pathlib import Path
from typing import Any

from crow_ovk_reporting import (
    ReportingRepository,
    TimeCategory,
    append_time_adjustment,
    append_time_segment,
    calculated_hours,
    reported_hours,
)
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response


def ovk_time_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    repository = ReportingRepository(data_root)

    @router.get("/ovk/tid", response_class=HTMLResponse)
    def time_page() -> str:
        return _asset_text("time.html")

    @router.get("/ovk/tid/app.js", response_class=Response)
    def time_app() -> Response:
        return Response(_asset_text("time.js"), media_type="application/javascript")

    @router.get("/ovk/falt/time.js", response_class=Response)
    def field_time_app() -> Response:
        return Response(
            _asset_text("field-time.js"),
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )

    @router.post("/api/ovk/reporting/time/{inspection_id}/segments", response_model=None)
    def append_segment(inspection_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            ledger = append_time_segment(
                repository,
                inspection_id=inspection_id,
                project_id=str(payload["project_id"]),
                inspection_date=str(payload["inspection_date"]),
                category=TimeCategory(str(payload["category"])),
                started_at=str(payload["started_at"]),
                ended_at=str(payload["ended_at"]),
                segment_id=_optional_text(payload.get("segment_id")),
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_TIME_SEGMENT", "message": str(exc)},
            ) from exc
        return _summary(ledger)

    @router.post("/api/ovk/reporting/time/{inspection_id}/adjustments", response_model=None)
    def append_adjustment(inspection_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            hours = Decimal(str(payload["hours"]))
            ledger = append_time_adjustment(
                repository,
                inspection_id=inspection_id,
                project_id=str(payload["project_id"]),
                inspection_date=str(payload["inspection_date"]),
                hours=hours,
                reason=str(payload["reason"]),
                changed_by=str(payload["changed_by"]),
                changed_at=_optional_text(payload.get("changed_at")),
                adjustment_id=_optional_text(payload.get("adjustment_id")),
            )
        except (InvalidOperation, KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_TIME_ADJUSTMENT", "message": str(exc)},
            ) from exc
        return _summary(ledger)

    return router


def _summary(ledger: Any) -> dict[str, Any]:
    return {
        "inspection_id": ledger.inspection_id,
        "calculated_hours": str(calculated_hours(ledger)),
        "reported_hours": str(reported_hours(ledger)),
        "segments": len(ledger.segments),
        "adjustments": len(ledger.adjustments),
    }


def _asset_text(name: str) -> str:
    return resources.files("crow_ovk_module").joinpath("assets", name).read_text(encoding="utf-8")


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
