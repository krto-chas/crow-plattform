"""Protokollutkast från fältdata (pass 110).

POST bygger utkastet ur senaste synkade fältsnapshot: grupperade
anmärkningar med positionskoder, deriverat besiktningsresultat och
täckningsförslag, samt sparar ett workflow-record som resten av kedjan
(granskning, PDF, intyg) arbetar vidare på.
"""

from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from crow_ovk_workflow import (
    OvkWorkflowRepository,
    bridge_inspection_inputs,
    build_protokoll_utkast,
    build_record,
    record_to_payload,
    utkast_to_payload,
)
from crow_ovk_workflow.flow_protocol import build_flow_protocol

from .ovk_draft_archive import (
    archive,
    has_unsaved_work,
    list_archived,
    load_archived,
    mark_built,
)
from .ovk_draft_archive import summary as draft_summary
from .ovk_field_surface import (
    _field_data_from_payload,
    _FieldSyncRepository,
    _validate_identifier,
    _verify_followup_sources,
)
from .ovk_field_workbench import _FieldWorkbenchRepository, _project_photo
from .ovk_issuance_lock import inspection_mutation_guard
from .ovk_protocol_source import save_protocol_source


def ovk_protokoll_router(data_root: Path) -> APIRouter:
    router = APIRouter(dependencies=[Depends(inspection_mutation_guard(data_root))])
    workflow_repository = OvkWorkflowRepository(data_root)

    @router.post(
        "/api/ovk/projects/{project_id}/field/{inspection_id}/protokoll-utkast",
        response_model=None,
    )
    async def create_protokoll_utkast(
        project_id: str, inspection_id: str, request: Request
    ) -> dict[str, Any]:
        raw = await request.body()
        confirmed = False
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
            if "confirm_replace" in parsed and not isinstance(parsed["confirm_replace"], bool):
                raise HTTPException(
                    status_code=422,
                    detail={"code": "INVALID_JSON", "message": "confirm_replace must be a boolean"},
                )
            confirmed = parsed.get("confirm_replace") is True

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
            if (
                photo.get("sync_status") != "synced"
                or not _project_photo(contexts, inspection_id, photo)["verified"]
            ):
                raise HTTPException(status_code=422, detail="Unverified field photo")
        utkast = build_protokoll_utkast(data)
        units = {unit.unit_id: unit.display_number for unit in data.units}
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
        system_ids = {system.system_id for system in existing.inspection.systems}
        if any(
            item.system_id is not None and item.system_id not in system_ids
            for item in data.measurements
        ):
            raise HTTPException(status_code=422, detail="Field measurement system mismatch")
        try:
            inputs = bridge_inspection_inputs(data, utkast, ovk_object=ovk_object)
            flow_protocol = build_flow_protocol(data)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        record = build_record(
            inspection_id=str(inputs["inspection_id"]),
            ovk_object=ovk_object,
            systems=existing.inspection.systems,
            checkpoints=inputs["checkpoints"],  # type: ignore[arg-type]
            measurements=inputs["measurements"],  # type: ignore[arg-type]
            findings=inputs["findings"],  # type: ignore[arg-type]
            actions=inputs["actions"],  # type: ignore[arg-type]
            coverage=utkast.suggested_coverage,
            planning=existing.planning,
            review=(),
        )
        # Posten ersätts. Har den ändrats sedan den senast byggdes ska det
        # bekräftas, och den sparas undan först så att arbetet går att ta tillbaka.
        saved_draft: str | None = None
        if has_unsaved_work(data_root, existing):
            if not confirmed:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "OVK_DRAFT_REPLACE_CONFIRMATION_REQUIRED",
                        "summary": draft_summary(existing),
                    },
                )
            saved_draft = archive(data_root, existing, "ersatt av nytt utkast")
        workflow_repository.save(record)
        record = workflow_repository.load(project_id, inspection_id)
        save_protocol_source(data_root, project_id, inspection_id, record)
        mark_built(data_root, record)

        canonical = json.dumps(
            utkast_to_payload(utkast), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return {
            "snapshot_sha256": revision,
            "sparat_utkast": saved_draft,
            "utkast": utkast_to_payload(utkast),
            "utkast_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
            "record": record_to_payload(record),
            "followup_review": followup_review,
            "flow_protocol": flow_protocol,
            "measurement_review": [
                {
                    "measurement_id": item.measurement_id,
                    "unit_id": item.unit_id,
                    "unit_number": units.get(item.unit_id),
                    "room_id": item.room_id,
                    "point_label": item.point_label,
                    "system_id": item.system_id,
                    "finding_id": item.finding_id,
                    "status": (
                        "pending"
                        if item.is_pending
                        else "measured"
                        if item.measurable
                        else "not_measurable"
                    ),
                    "reason": item.not_measurable_reason,
                }
                for item in data.measurements
            ],
            "note": (
                "Utkast: täckningsförslaget kräver systemförteckningsbekräftelse "
                "(STATED) innan protokollet kan färdigställas."
            ),
        }

    @router.get(
        "/api/ovk/projects/{project_id}/field/{inspection_id}/protokoll-utkast/sparade",
        response_model=None,
    )
    def list_saved_drafts(project_id: str, inspection_id: str) -> dict[str, Any]:
        _validate_identifier(project_id)
        _validate_identifier(inspection_id)
        return {
            "project_id": project_id,
            "inspection_id": inspection_id,
            "sparade": list_archived(data_root, project_id, inspection_id),
        }

    @router.post(
        "/api/ovk/projects/{project_id}/field/{inspection_id}/protokoll-utkast/sparade/"
        "{archive_id}/aterstall",
        response_model=None,
    )
    def restore_saved_draft(project_id: str, inspection_id: str, archive_id: str) -> dict[str, Any]:
        _validate_identifier(project_id)
        _validate_identifier(inspection_id)
        try:
            existing = workflow_repository.load(project_id, inspection_id)
            saved = load_archived(data_root, project_id, inspection_id, archive_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "OVK_SAVED_DRAFT_NOT_FOUND"}
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=409, detail={"code": "OVK_SAVED_DRAFT_UNREADABLE"}
            ) from exc
        # Det som ligger i posten nu sparas undan på samma sätt, så att
        # återställningen själv går att ångra.
        replaced = (
            archive(data_root, existing, "ersatt vid återställning")
            if has_unsaved_work(data_root, existing)
            else None
        )
        # Planeringen är besiktningens nuvarande; den sparade kopian kan vara äldre.
        workflow_repository.save(replace(saved, planning=existing.planning))
        record = workflow_repository.load(project_id, inspection_id)
        return {
            "aterstallt": archive_id,
            "sparat_utkast": replaced,
            "record": record_to_payload(record),
        }

    return router
