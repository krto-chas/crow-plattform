from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from crow_offer_export.evaluation_protocol import build_evaluation_protocol_workbook
from crow_pressure_test.vent_bridge import candidate_from_riser_string, candidate_to_payload
from crow_riser_model.models import RiserString

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def pressure_test_integration_router() -> APIRouter:
    router = APIRouter()

    @router.post(
        "/api/provtryckning/projects/{project_id}/vent-candidates",
        response_model=None,
    )
    async def vent_candidates(project_id: str, request: Request) -> dict[str, Any]:
        del project_id
        payload: Any = await request.json()
        raw_strings = payload.get("strings") if isinstance(payload, dict) else None
        if not isinstance(raw_strings, list):
            raise HTTPException(status_code=422, detail={"code": "INVALID_VENT_MODEL_INPUT"})

        candidates: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        for index, raw in enumerate(raw_strings):
            try:
                item = _riser_string(raw)
                candidates.append(candidate_to_payload(candidate_from_riser_string(item)))
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                skipped.append({"index": str(index), "reason": str(exc)})
        return {
            "schema_version": "crow-pressure-test-vent-bridge-v0.1",
            "candidates": candidates,
            "skipped": skipped,
        }

    @router.post(
        "/api/provtryckning/projects/{project_id}/protocol.xlsx",
        response_model=None,
    )
    async def protocol_xlsx(project_id: str, request: Request) -> Response:
        payload: Any = await request.json()
        transport = httpx.ASGITransport(app=request.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://crow.internal",
        ) as client:
            evaluated = await client.post(
                f"/api/provtryckning/projects/{project_id}/evaluate",
                json=payload,
            )
        if evaluated.status_code != 200:
            return Response(
                content=evaluated.content,
                status_code=evaluated.status_code,
                media_type="application/json",
            )
        result = evaluated.json()
        if not bool(result.get("ready_for_protocol")):
            raise HTTPException(
                status_code=409,
                detail={"code": "PRESSURE_TEST_NOT_PROTOCOL_READY"},
            )
        workbook = build_evaluation_protocol_workbook(result)
        filename = f"crow-provtryckning-{project_id}.xlsx"
        return Response(
            content=workbook,
            media_type=_XLSX_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return router


def _riser_string(raw: object) -> RiserString:
    if not isinstance(raw, dict):
        raise TypeError("riser string must be an object")
    evidence = raw.get("evidence", {})
    if not isinstance(evidence, dict):
        raise TypeError("evidence must be an object")
    return RiserString(
        apartment_id=str(raw["apartment_id"]),
        stairwell_id=str(raw["stairwell_id"]),
        kind=str(raw["kind"]),
        plan=str(raw.get("plan", "")),
        dimension=str(raw["dimension"]),
        length_m=Decimal(str(raw["length_m"])),
        evidence=evidence,
    )
