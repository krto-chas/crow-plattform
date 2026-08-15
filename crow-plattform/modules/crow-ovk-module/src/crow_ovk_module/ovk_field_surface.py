from __future__ import annotations

import json
import re
from hashlib import sha256
from importlib import resources
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from crow_ovk import CheckStatus, EvidenceOrigin, FindingSeverity
from crow_ovk_field import (
    FieldCheckpoint,
    FieldFinding,
    FieldInspectionData,
    FieldMeasurement,
    FieldRoom,
    FieldUnit,
    KeyLog,
    MeasurePointType,
    OvkPhotoEvidence,
    PhotoSyncStatus,
    TechnicalSpace,
    TechnicalSpaceKind,
    UnitKind,
    UnitStatus,
    WindowVentCheck,
    load_checklists,
    load_defect_types,
    nameplate_missing_spaces,
    parse_flow_value,
    validate_field_data,
)

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def ovk_field_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    repository = _FieldSyncRepository(data_root)

    @router.get("/ovk/falt", response_class=HTMLResponse)
    def field_page() -> str:
        return _asset_text("field.html")

    @router.get("/ovk/falt/app.js", response_class=Response)
    def field_app() -> Response:
        return Response(_asset_text("field.js"), media_type="application/javascript")

    @router.get("/ovk/falt/sw.js", response_class=Response)
    def field_service_worker() -> Response:
        return Response(
            _asset_text("field-sw.js"),
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": "/ovk/", "Cache-Control": "no-cache"},
        )

    @router.get("/api/ovk/field/checklists", response_model=None)
    def field_checklists() -> dict[str, Any]:
        return {
            "checklists": {
                kind.value: [{"id": item.item_id, "label": item.label} for item in items]
                for kind, items in load_checklists().items()
            }
        }

    @router.get("/api/ovk/field/defect-types", response_model=None)
    def defect_types() -> dict[str, Any]:
        return {
            "defect_types": [
                {
                    "id": item.defect_id,
                    "label": item.label,
                    "description": item.description,
                    "default_rule_refs": list(item.default_rule_refs),
                }
                for item in load_defect_types()
            ]
        }

    @router.post("/api/ovk/field/validate", response_model=None)
    async def validate_field_payload(request: Request) -> dict[str, Any]:
        data = _validated_payload(await request.json())
        return _validation_summary(data)

    @router.put("/api/ovk/field/sync/{inspection_id}", response_model=None)
    async def sync_field_payload(inspection_id: str, request: Request) -> dict[str, Any]:
        _validate_identifier(inspection_id)
        payload: Any = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_FIELD_DATA"})
        if str(payload.get("inspection_id", "")) != inspection_id:
            raise HTTPException(
                status_code=409,
                detail={"code": "OVK_FIELD_INSPECTION_MISMATCH"},
            )
        data = _validated_payload(payload)
        normalized = _field_data_to_payload(data)
        snapshot_sha256 = repository.save(inspection_id, normalized)
        return {
            **_validation_summary(data),
            "snapshot_sha256": snapshot_sha256,
            "media_pending": sum(
                photo.sync_status is not PhotoSyncStatus.SYNCED for photo in data.photos
            ),
            "synced": True,
        }

    @router.get("/api/ovk/field/sync/{inspection_id}", response_model=None)
    def get_synced_field_payload(inspection_id: str) -> dict[str, Any]:
        _validate_identifier(inspection_id)
        try:
            payload, digest = repository.load(inspection_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "OVK_FIELD_SNAPSHOT_NOT_FOUND"},
            ) from exc
        return {"inspection_id": inspection_id, "snapshot_sha256": digest, "payload": payload}

    return router


def _validated_payload(payload: Any) -> FieldInspectionData:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_FIELD_DATA"})
    try:
        data = _field_data_from_payload(payload)
        validate_field_data(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_OVK_FIELD_DATA", "message": str(exc)},
        ) from exc
    return data


def _validation_summary(data: FieldInspectionData) -> dict[str, Any]:
    status_counts = {status.value: 0 for status in UnitStatus}
    for unit in data.units:
        status_counts[unit.status.value] += 1
    return {
        "inspection_id": data.inspection_id,
        "units": len(data.units),
        "rooms": len(data.rooms),
        "findings": len(data.findings),
        "photos": len(data.photos),
        "measurements": len(data.measurements),
        "window_vents": len(data.window_vents),
        "unit_status_counts": status_counts,
        "technical_spaces": len(data.technical_spaces),
        "checkpoints": len(data.checkpoints),
        "checkpoint_failures": sum(item.status is CheckStatus.FAIL for item in data.checkpoints),
        "nameplates_missing": list(nameplate_missing_spaces(data)),
        "coverage_complete": bool(data.units) and status_counts["ej_paborjad"] == 0,
        "valid": True,
    }


def _field_data_from_payload(payload: dict[str, Any]) -> FieldInspectionData:
    inspection_id = str(payload["inspection_id"])
    units = tuple(
        FieldUnit(
            unit_id=str(item["unit_id"]),
            inspection_id=inspection_id,
            number=str(item["number"]),
            kind=UnitKind(str(item.get("kind", "apartment"))),
            label=str(item.get("label", "")),
            status=UnitStatus(str(item.get("status", "ej_paborjad"))),
            checked_at=_optional_str(item.get("checked_at")),
            bom_at=_optional_str(item.get("bom_at")),
            bom_note=str(item.get("bom_note", "")),
            key=_key_from_payload(item.get("key")),
            system_type=_optional_str(item.get("system_type")),
        )
        for item in _dict_items(payload.get("units", []), "units")
    )
    rooms = tuple(
        FieldRoom(
            room_id=str(item["room_id"]),
            unit_id=str(item["unit_id"]),
            name=str(item["name"]),
        )
        for item in _dict_items(payload.get("rooms", []), "rooms")
    )
    findings = tuple(
        FieldFinding(
            finding_id=str(item["finding_id"]),
            inspection_id=inspection_id,
            unit_id=str(item["unit_id"]),
            defect_type=str(item["defect_type"]),
            description=str(item.get("description", "")),
            severity=FindingSeverity(str(item.get("severity", "info"))),
            room_id=_optional_str(item.get("room_id")),
            checkpoint_id=_optional_str(item.get("checkpoint_id")),
            system_id=_optional_str(item.get("system_id")),
            rule_refs=tuple(str(value) for value in item.get("rule_refs", [])),
            origin=EvidenceOrigin(str(item.get("origin", "observed"))),
        )
        for item in _dict_items(payload.get("findings", []), "findings")
    )
    photos = tuple(
        OvkPhotoEvidence(
            photo_id=str(item["photo_id"]),
            inspection_id=inspection_id,
            unit_id=str(item.get("unit_id", "")),
            unit_number=str(item.get("unit_number", "")),
            defect_type=str(item["defect_type"]),
            captured_at=str(item["captured_at"]),
            captured_by=str(item["captured_by"]),
            local_uri=str(item["local_uri"]),
            sha256=str(item["sha256"]),
            mime_type=str(item["mime_type"]),
            room_id=_optional_str(item.get("room_id")),
            finding_id=_optional_str(item.get("finding_id")),
            checkpoint_id=_optional_str(item.get("checkpoint_id")),
            system_id=_optional_str(item.get("system_id")),
            space_id=_optional_str(item.get("space_id")),
            description=str(item.get("description", "")),
            rule_refs=tuple(str(value) for value in item.get("rule_refs", [])),
            sync_status=PhotoSyncStatus(str(item.get("sync_status", "local"))),
        )
        for item in _dict_items(payload.get("photos", []), "photos")
    )
    measurements = tuple(
        FieldMeasurement(
            measurement_id=str(item["measurement_id"]),
            inspection_id=inspection_id,
            unit_id=str(item["unit_id"]),
            point_type=MeasurePointType(str(item["point_type"])),
            point_label=str(item["point_label"]),
            room_id=_optional_str(item.get("room_id")),
            measurable=bool(item.get("measurable", True)),
            measured_value=parse_flow_value(item.get("measured_value")),
            designed_value=parse_flow_value(item.get("designed_value")),
            unit_of_measure=str(item.get("unit_of_measure", "l/s")),
            not_measurable_reason=str(item.get("not_measurable_reason", "")),
            finding_id=_optional_str(item.get("finding_id")),
        )
        for item in _dict_items(payload.get("measurements", []), "measurements")
    )
    window_vents = tuple(
        WindowVentCheck(
            check_id=str(item["check_id"]),
            inspection_id=inspection_id,
            unit_id=str(item["unit_id"]),
            present=bool(item.get("present", False)),
            room_id=_optional_str(item.get("room_id")),
            note=str(item.get("note", "")),
        )
        for item in _dict_items(payload.get("window_vents", []), "window_vents")
    )
    technical_spaces = tuple(
        TechnicalSpace(
            space_id=str(item["space_id"]),
            inspection_id=inspection_id,
            kind=TechnicalSpaceKind(str(item["kind"])),
            label=str(item["label"]),
            location=str(item.get("location", "")),
            system_id=_optional_str(item.get("system_id")),
        )
        for item in _dict_items(payload.get("technical_spaces", []), "technical_spaces")
    )
    checkpoints = tuple(
        FieldCheckpoint(
            checkpoint_id=str(item["checkpoint_id"]),
            inspection_id=inspection_id,
            space_id=str(item["space_id"]),
            label=str(item["label"]),
            status=CheckStatus(str(item.get("status", "pass"))),
            note=str(item.get("note", "")),
        )
        for item in _dict_items(payload.get("checkpoints", []), "checkpoints")
    )
    return FieldInspectionData(
        inspection_id=inspection_id,
        units=units,
        rooms=rooms,
        findings=findings,
        photos=photos,
        measurements=measurements,
        window_vents=window_vents,
        technical_spaces=technical_spaces,
        checkpoints=checkpoints,
    )


def _key_from_payload(value: Any) -> KeyLog | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("key must be an object")
    return KeyLog(
        received=bool(value.get("received", False)),
        received_at=_optional_str(value.get("received_at")),
        returned=bool(value.get("returned", False)),
        returned_at=_optional_str(value.get("returned_at")),
        master_key_used=bool(value.get("master_key_used", False)),
        master_key_note=str(value.get("master_key_note", "")),
    )


def _field_data_to_payload(data: FieldInspectionData) -> dict[str, Any]:
    return {
        "inspection_id": data.inspection_id,
        "units": [
            {
                "unit_id": item.unit_id,
                "number": item.number,
                "kind": item.kind.value,
                "label": item.label,
                "status": item.status.value,
                "checked_at": item.checked_at,
                "bom_at": item.bom_at,
                "bom_note": item.bom_note,
                "system_type": item.system_type,
                "key": (
                    {
                        "received": item.key.received,
                        "received_at": item.key.received_at,
                        "returned": item.key.returned,
                        "returned_at": item.key.returned_at,
                        "master_key_used": item.key.master_key_used,
                        "master_key_note": item.key.master_key_note,
                    }
                    if item.key is not None
                    else None
                ),
            }
            for item in data.units
        ],
        "rooms": [
            {"room_id": item.room_id, "unit_id": item.unit_id, "name": item.name}
            for item in data.rooms
        ],
        "findings": [
            {
                "finding_id": item.finding_id,
                "unit_id": item.unit_id,
                "defect_type": item.defect_type,
                "description": item.description,
                "severity": item.severity.value,
                "room_id": item.room_id,
                "checkpoint_id": item.checkpoint_id,
                "system_id": item.system_id,
                "rule_refs": list(item.rule_refs),
                "origin": item.origin.value,
            }
            for item in data.findings
        ],
        "photos": [
            {
                "photo_id": item.photo_id,
                "unit_id": item.unit_id,
                "unit_number": item.unit_number,
                "defect_type": item.defect_type,
                "captured_at": item.captured_at,
                "captured_by": item.captured_by,
                "local_uri": item.local_uri,
                "sha256": item.sha256,
                "mime_type": item.mime_type,
                "room_id": item.room_id,
                "finding_id": item.finding_id,
                "checkpoint_id": item.checkpoint_id,
                "system_id": item.system_id,
                "space_id": item.space_id,
                "description": item.description,
                "rule_refs": list(item.rule_refs),
                "sync_status": item.sync_status.value,
            }
            for item in data.photos
        ],
        "measurements": [
            {
                "measurement_id": item.measurement_id,
                "unit_id": item.unit_id,
                "point_type": item.point_type.value,
                "point_label": item.point_label,
                "room_id": item.room_id,
                "measurable": item.measurable,
                "measured_value": (
                    str(item.measured_value) if item.measured_value is not None else None
                ),
                "designed_value": (
                    str(item.designed_value) if item.designed_value is not None else None
                ),
                "unit_of_measure": item.unit_of_measure,
                "not_measurable_reason": item.not_measurable_reason,
                "finding_id": item.finding_id,
                "origin": item.origin.value,
            }
            for item in data.measurements
        ],
        "window_vents": [
            {
                "check_id": item.check_id,
                "unit_id": item.unit_id,
                "present": item.present,
                "room_id": item.room_id,
                "note": item.note,
            }
            for item in data.window_vents
        ],
        "technical_spaces": [
            {
                "space_id": item.space_id,
                "kind": item.kind.value,
                "label": item.label,
                "location": item.location,
                "system_id": item.system_id,
            }
            for item in data.technical_spaces
        ],
        "checkpoints": [
            {
                "checkpoint_id": item.checkpoint_id,
                "space_id": item.space_id,
                "label": item.label,
                "status": item.status.value,
                "note": item.note,
            }
            for item in data.checkpoints
        ],
    }


def _dict_items(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TypeError(f"{name} must be a list of objects")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _validate_identifier(value: str) -> None:
    if not _SAFE_ID.fullmatch(value):
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"})


def _asset_text(name: str) -> str:
    return resources.files("crow_ovk_module").joinpath("assets", name).read_text(encoding="utf-8")


class _FieldSyncRepository:
    def __init__(self, data_root: Path) -> None:
        self._root = data_root / "ovk-field-sync"

    def save(self, inspection_id: str, payload: dict[str, Any]) -> str:
        _validate_identifier(inspection_id)
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = sha256(canonical.encode("utf-8")).hexdigest()
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._root / f"{inspection_id}.json"
        temporary = self._root / f".{inspection_id}.tmp"
        temporary.write_text(canonical + "\n", encoding="utf-8")
        temporary.replace(target)
        return digest

    def load(self, inspection_id: str) -> tuple[dict[str, Any], str]:
        _validate_identifier(inspection_id)
        target = self._root / f"{inspection_id}.json"
        canonical = target.read_text(encoding="utf-8").rstrip("\n")
        payload: Any = json.loads(canonical)
        if not isinstance(payload, dict):
            raise ValueError("OVK field snapshot must contain an object")
        digest = sha256(canonical.encode("utf-8")).hexdigest()
        return payload, digest
