"""Protokollutkast från fältdata (pass 110).

POST bygger utkastet ur senaste synkade fältsnapshot: grupperade
anmärkningar med positionskoder, deriverat besiktningsresultat och
täckningsförslag, samt sparar ett workflow-record som resten av kedjan
(granskning, PDF, intyg) arbetar vidare på.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from crow_ovk import OvkObject, VentilationSystemRef
from crow_ovk_workflow import (
    OvkWorkflowRepository,
    bridge_inspection_inputs,
    build_protokoll_utkast,
    build_record,
    record_to_payload,
    utkast_to_payload,
)

from .ovk_field_surface import _field_data_from_payload


def ovk_protokoll_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    workflow_repository = OvkWorkflowRepository(data_root)
    snapshot_root = data_root / "ovk-field-sync"

    def _load_snapshot(inspection_id: str) -> dict[str, Any]:
        target = snapshot_root / f"{inspection_id}.json"
        if not target.exists():
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "FIELD_SNAPSHOT_NOT_FOUND",
                    "message": "Ingen synkad fältdata för besiktningen.",
                },
            )
        payload: Any = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_SNAPSHOT", "message": "Snapshot är inte ett objekt."},
            )
        return payload

    @router.post(
        "/api/ovk/projects/{project_id}/field/{inspection_id}/protokoll-utkast",
        response_model=None,
    )
    async def create_protokoll_utkast(
        project_id: str, inspection_id: str, request: Request
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        raw = await request.body()
        if raw:
            parsed: Any = json.loads(raw)
            if not isinstance(parsed, dict):
                raise HTTPException(
                    status_code=422,
                    detail={"code": "INVALID_JSON", "message": "payload must be an object"},
                )
            body = parsed

        snapshot = _load_snapshot(inspection_id)
        try:
            snapshot.setdefault("inspection_id", inspection_id)
            data = _field_data_from_payload(snapshot)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_FIELD_DATA", "message": str(exc)},
            ) from exc

        utkast = build_protokoll_utkast(data)

        system_type = str(body.get("system_type") or snapshot.get("system_type") or "F")
        building_id = str(body.get("building_id") or "byggnad-1")
        object_name = str(body.get("object_name") or inspection_id)
        ovk_object = OvkObject(
            object_id=f"{inspection_id}-objekt",
            project_id=project_id,
            building_id=building_id,
            name=object_name,
            address=None,
        )
        inputs = bridge_inspection_inputs(data, utkast, ovk_object=ovk_object)
        record = build_record(
            inspection_id=str(inputs["inspection_id"]),
            ovk_object=ovk_object,
            systems=(
                VentilationSystemRef(f"{system_type}01", system_type, f"System {system_type}01"),
            ),
            checkpoints=inputs["checkpoints"],  # type: ignore[arg-type]
            findings=inputs["findings"],  # type: ignore[arg-type]
            actions=inputs["actions"],  # type: ignore[arg-type]
            coverage=utkast.suggested_coverage,
        )
        workflow_repository.save(record)

        canonical = json.dumps(
            utkast_to_payload(utkast), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return {
            "utkast": utkast_to_payload(utkast),
            "utkast_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
            "record": record_to_payload(record),
            "note": (
                "Utkast: täckningsförslaget kräver systemförteckningsbekräftelse "
                "(STATED) innan protokollet kan färdigställas."
            ),
        }

    return router
