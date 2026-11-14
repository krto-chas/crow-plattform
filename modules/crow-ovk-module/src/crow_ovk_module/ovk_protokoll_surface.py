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

from crow_ovk_workflow import (
    OvkWorkflowRepository,
    bridge_inspection_inputs,
    build_protokoll_utkast,
    build_record,
    record_to_payload,
    utkast_to_payload,
)

from .ovk_field_surface import (
    _field_data_from_payload,
    _FieldSyncRepository,
    _validate_identifier,
    _verify_followup_sources,
)
from .ovk_field_workbench import _FieldWorkbenchRepository, _project_photo


def ovk_protokoll_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    workflow_repository = OvkWorkflowRepository(data_root)

    @router.post(
        "/api/ovk/projects/{project_id}/field/{inspection_id}/protokoll-utkast",
        response_model=None,
    )
    async def create_protokoll_utkast(
        project_id: str, inspection_id: str, request: Request
    ) -> dict[str, Any]:
        raw = await request.body()
        if raw:
            try:
                parsed: Any = json.loads(raw)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Invalid JSON") from exc
            if not isinstance(parsed, dict):
                raise HTTPException(
                    status_code=422,
                    detail={"code": "INVALID_JSON", "message": "payload must be an object"},
                )

        _validate_identifier(project_id)
        _validate_identifier(inspection_id)
        sync_repository = _FieldSyncRepository(data_root, project_id=project_id)
        contexts = _FieldWorkbenchRepository(data_root, project_id=project_id)
        try:
            existing = workflow_repository.load(project_id, inspection_id)
            snapshot, revision = sync_repository.load(inspection_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Scoped field data unavailable") from exc
        if existing.planning is None or existing.inspection.ovk_object.project_id != project_id:
            raise HTTPException(status_code=422, detail="Planned workflow required")
        if snapshot.get("inspection_id") != inspection_id:
            raise HTTPException(status_code=409, detail="Field inspection mismatch")
        if request.headers.get("X-OVK-Base-Revision") != revision:
            raise HTTPException(status_code=409, detail="Field revision mismatch")
        try:
            data = _field_data_from_payload(snapshot)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_FIELD_DATA", "message": str(exc)},
            ) from exc

        _verify_followup_sources(data_root, data, sync_repository, project_id=project_id)
        context = contexts.load_context_optional(inspection_id)
        if context is None or context.get("inspector_id") != existing.planning.inspector_id:
            raise HTTPException(status_code=422, detail="Verified field context required")
        if context.get("previous_inspection_id") != existing.planning.previous_inspection_id:
            raise HTTPException(status_code=409, detail="Field predecessor mismatch")
        if context.get("system_type") not in {
            system.system_type for system in existing.inspection.systems
        }:
            raise HTTPException(status_code=422, detail="Field system mismatch")
        for photo in snapshot.get("photos", []):
            if photo.get("sync_status") != "synced" or not _project_photo(
                contexts, inspection_id, photo
            )["verified"]:
                raise HTTPException(status_code=422, detail="Unverified field photo")
        utkast = build_protokoll_utkast(data)
        units = {unit.unit_id: unit.number for unit in data.units}
        photos = {photo["photo_id"]: photo for photo in snapshot.get("photos", [])}
        followup_review = [
            {
                "source_inspection_id": item.source_inspection_id,
                "source_finding_id": item.source_finding_id,
                "unit_number": units[item.unit_id],
                "status": item.status,
                "note": item.note,
                "current_finding_id": item.current_finding_id,
                "photos": [
                    _project_photo(contexts, inspection_id, photos[photo_id])
                    for photo_id in item.photo_ids
                ],
            }
            for item in data.finding_followups
        ]

        ovk_object = existing.inspection.ovk_object
        inputs = bridge_inspection_inputs(data, utkast, ovk_object=ovk_object)
        record = build_record(
            inspection_id=str(inputs["inspection_id"]),
            ovk_object=ovk_object,
            systems=existing.inspection.systems,
            checkpoints=inputs["checkpoints"],  # type: ignore[arg-type]
            findings=inputs["findings"],  # type: ignore[arg-type]
            actions=inputs["actions"],  # type: ignore[arg-type]
            coverage=utkast.suggested_coverage,
            planning=existing.planning,
            review=(),
        )
        workflow_repository.save(record)

        canonical = json.dumps(
            utkast_to_payload(utkast), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return {
            "snapshot_sha256": revision,
            "utkast": utkast_to_payload(utkast),
            "utkast_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
            "record": record_to_payload(record),
            "followup_review": followup_review,
            "note": (
                "Utkast: täckningsförslaget kräver systemförteckningsbekräftelse "
                "(STATED) innan protokollet kan färdigställas."
            ),
        }

    return router
