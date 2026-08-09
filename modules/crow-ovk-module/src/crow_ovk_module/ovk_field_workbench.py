from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def ovk_field_workbench_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    repository = _FieldWorkbenchRepository(data_root)

    @router.put("/api/ovk/field/context/{inspection_id}", response_model=None)
    async def save_field_context(inspection_id: str, request: Request) -> dict[str, Any]:
        _validate_identifier(inspection_id)
        payload: Any = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_FIELD_CONTEXT"})
        project_id = _optional_text(payload.get("project_id"))
        inspector = _optional_text(payload.get("inspector"))
        previous_inspection_id = _optional_text(payload.get("previous_inspection_id"))
        if project_id is None or inspector is None:
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_FIELD_CONTEXT"})
        if previous_inspection_id is not None:
            _validate_identifier(previous_inspection_id)
            if previous_inspection_id == inspection_id:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "OVK_FIELD_SELF_PREDECESSOR"},
                )
        context = {
            "inspection_id": inspection_id,
            "project_id": project_id,
            "inspector": inspector,
            "previous_inspection_id": previous_inspection_id,
            "saved_at": datetime.now(UTC).isoformat(),
        }
        repository.save_context(inspection_id, context)
        return context

    @router.get("/api/ovk/field/workbench/{inspection_id}", response_model=None)
    def field_workbench(inspection_id: str) -> dict[str, Any]:
        _validate_identifier(inspection_id)
        try:
            snapshot, snapshot_sha256 = repository.load_snapshot(inspection_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "OVK_FIELD_SNAPSHOT_NOT_FOUND"},
            ) from exc
        return _project_snapshot(repository, snapshot, snapshot_sha256)

    return router


def _project_snapshot(
    repository: _FieldWorkbenchRepository,
    snapshot: dict[str, Any],
    snapshot_sha256: str,
) -> dict[str, Any]:
    inspection_id = str(snapshot.get("inspection_id", ""))
    context_map = repository.load_context_optional(inspection_id) or {}
    rooms = _object_list(snapshot.get("rooms"))
    findings = _object_list(snapshot.get("findings"))
    photos = _object_list(snapshot.get("photos"))
    room_by_id = {str(item.get("room_id", "")): item for item in rooms}

    projected_findings: list[dict[str, Any]] = []
    for finding in findings:
        finding_id = str(finding.get("finding_id", ""))
        room_id = _optional_text(finding.get("room_id"))
        room = room_by_id.get(room_id or "")
        projected_findings.append(
            {
                **finding,
                "room_name": None if room is None else _optional_text(room.get("name")),
                "photos": [
                    _project_photo(repository, inspection_id, photo)
                    for photo in photos
                    if str(photo.get("finding_id", "")) == finding_id
                ],
            }
        )

    units = []
    for unit in _object_list(snapshot.get("units")):
        unit_id = str(unit.get("unit_id", ""))
        units.append(
            {
                **unit,
                "rooms": [room for room in rooms if str(room.get("unit_id", "")) == unit_id],
                "findings": [
                    finding
                    for finding in projected_findings
                    if str(finding.get("unit_id", "")) == unit_id
                ],
            }
        )

    all_projected_photos = [_project_photo(repository, inspection_id, photo) for photo in photos]
    verified_photos = sum(1 for photo in all_projected_photos if photo["verified"])
    return {
        "inspection_id": inspection_id,
        "project_id": _optional_text(context_map.get("project_id")),
        "inspector": _optional_text(context_map.get("inspector")),
        "previous_inspection_id": _optional_text(context_map.get("previous_inspection_id")),
        "saved_at": _optional_text(context_map.get("saved_at")),
        "snapshot_sha256": snapshot_sha256,
        "counts": {
            "units": len(units),
            "rooms": len(rooms),
            "findings": len(findings),
            "photos": len(photos),
            "verified_photos": verified_photos,
        },
        "units": units,
        "orphan_photos": [
            photo
            for photo in all_projected_photos
            if not any(
                str(finding.get("finding_id", "")) == str(photo.get("finding_id", ""))
                for finding in findings
            )
        ],
    }


def _project_photo(
    repository: _FieldWorkbenchRepository,
    inspection_id: str,
    photo: dict[str, Any],
) -> dict[str, Any]:
    photo_id = str(photo.get("photo_id", ""))
    expected_sha256 = str(photo.get("sha256", "")).lower()
    receipt = repository.load_receipt_optional(inspection_id, photo_id)
    receipt_data = receipt or {}
    verified = bool(
        receipt
        and compare_digest(str(receipt_data.get("sha256", "")).lower(), expected_sha256)
        and str(receipt_data.get("inspection_id", "")) == inspection_id
        and str(receipt_data.get("photo_id", "")) == photo_id
    )
    return {
        **photo,
        "verified": verified,
        "media_id": None if not verified else receipt_data.get("media_id"),
        "evidence_id": None if not verified else receipt_data.get("evidence_id"),
        "size_bytes": None if not verified else receipt_data.get("size_bytes"),
        "content_url": (
            None if not verified else f"/api/ovk/field/media/{inspection_id}/{photo_id}/content"
        ),
    }


def _validate_identifier(value: str) -> None:
    if not _SAFE_ID.fullmatch(value):
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"})


def _object_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


class _FieldWorkbenchRepository:
    def __init__(self, data_root: Path) -> None:
        self._snapshot_root = data_root / "ovk-field-sync"
        self._media_root = data_root / "ovk-field-media"
        self._context_root = data_root / "ovk-field-context"

    def load_snapshot(self, inspection_id: str) -> tuple[dict[str, Any], str]:
        target = self._snapshot_root / f"{inspection_id}.json"
        canonical = target.read_text(encoding="utf-8").rstrip("\n")
        payload: Any = json.loads(canonical)
        if not isinstance(payload, dict):
            raise ValueError("OVK field snapshot must contain an object")
        return payload, sha256(canonical.encode()).hexdigest()

    def save_context(self, inspection_id: str, payload: dict[str, Any]) -> None:
        self._context_root.mkdir(parents=True, exist_ok=True)
        target = self._context_root / f"{inspection_id}.json"
        self._write_json(target, payload)

    def load_context_optional(self, inspection_id: str) -> dict[str, Any] | None:
        target = self._context_root / f"{inspection_id}.json"
        try:
            payload: Any = json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        return payload if isinstance(payload, dict) else None

    def load_receipt_optional(self, inspection_id: str, photo_id: str) -> dict[str, Any] | None:
        target = self._media_root / inspection_id / f"{photo_id}.json"
        try:
            payload: Any = json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _write_json(target: Path, payload: dict[str, Any]) -> None:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        temporary = target.with_name(f".{target.name}.tmp")
        temporary.write_text(canonical + "\n", encoding="utf-8")
        temporary.replace(target)
