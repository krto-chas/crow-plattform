from __future__ import annotations

import json
import re
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from crow_ovk_workflow.repository import OvkWorkflowRepository

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def ovk_field_history_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    repository = _FieldHistoryRepository(data_root)

    @router.get("/api/ovk/field/history", response_model=None)
    def list_history(project_id: str = Query(min_length=1)) -> dict[str, Any]:
        return {"project_id": project_id, "inspections": repository.list_project(project_id)}

    @router.get("/api/ovk/field/history/{inspection_id}", response_model=None)
    def restore_projection(inspection_id: str) -> dict[str, Any]:
        _validate_identifier(inspection_id)
        try:
            return repository.restore_projection(inspection_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "OVK_FIELD_HISTORY_NOT_FOUND"},
            ) from exc

    workflows = OvkWorkflowRepository(data_root)

    @router.get(
        "/api/ovk/projects/{project_id}/inspections/{inspection_id}/field-history",
        response_model=None,
    )
    def planned_history(project_id: str, inspection_id: str) -> dict[str, Any]:
        try:
            current = workflows.load(project_id, inspection_id)
            source_id = current.planning.previous_inspection_id if current.planning else None
            if source_id is None:
                return {"source_inspection_id": None, "historical_findings": []}
            source = workflows.load(project_id, source_id)
            if source.inspection.ovk_object != current.inspection.ovk_object:
                old = source.inspection.ovk_object
                new = current.inspection.ovk_object
                if (old.object_id, old.building_id) != (new.object_id, new.building_id):
                    raise ValueError("historical building mismatch")
            projection = repository.restore_projection(source_id)
            if projection["project_id"] != project_id:
                raise ValueError("historical field project mismatch")
            return projection
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail="Historical field data unavailable"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router


class _FieldHistoryRepository:
    def __init__(self, data_root: Path) -> None:
        self._snapshot_root = data_root / "ovk-field-sync"
        self._context_root = data_root / "ovk-field-context"
        self._media_root = data_root / "ovk-field-media"

    def list_project(self, project_id: str) -> list[dict[str, Any]]:
        if not self._context_root.exists():
            return []
        items: list[dict[str, Any]] = []
        for path in self._context_root.glob("*.json"):
            context = _read_object(path)
            if str(context.get("project_id", "")) != project_id:
                continue
            inspection_id = str(context.get("inspection_id", path.stem))
            snapshot_path = self._snapshot_root / f"{inspection_id}.json"
            if not snapshot_path.is_file():
                continue
            snapshot, digest = self._load_snapshot(inspection_id)
            items.append(
                {
                    "inspection_id": inspection_id,
                    "project_id": project_id,
                    "inspector": _optional_text(context.get("inspector")),
                    "inspection_date": _optional_text(context.get("inspection_date")),
                    "source_kind": _optional_text(context.get("source_kind")) or "field",
                    "previous_inspection_id": _optional_text(context.get("previous_inspection_id")),
                    "saved_at": _optional_text(context.get("saved_at")),
                    "snapshot_sha256": digest,
                    "counts": {
                        "units": len(_object_list(snapshot.get("units"))),
                        "rooms": len(_object_list(snapshot.get("rooms"))),
                        "findings": len(_object_list(snapshot.get("findings"))),
                        "photos": len(_object_list(snapshot.get("photos"))),
                    },
                }
            )
        items.sort(
            key=lambda item: (
                str(item.get("inspection_date") or item.get("saved_at") or ""),
                item["inspection_id"],
            ),
            reverse=True,
        )
        return items

    def restore_projection(self, inspection_id: str) -> dict[str, Any]:
        snapshot, digest = self._load_snapshot(inspection_id)
        context = _read_object(self._context_root / f"{inspection_id}.json")
        rooms = _object_list(snapshot.get("rooms"))
        photos = _object_list(snapshot.get("photos"))
        units = _object_list(snapshot.get("units"))
        historical_findings: list[dict[str, Any]] = []
        for finding in _object_list(snapshot.get("findings")):
            finding_id = str(finding.get("finding_id", ""))
            historical_findings.append(
                {
                    **finding,
                    "source_inspection_id": inspection_id,
                    "unit_number": next(
                        (
                            u.get("number")
                            for u in units
                            if u.get("unit_id") == finding.get("unit_id")
                        ),
                        None,
                    ),
                    "room_name": next(
                        (
                            r.get("name")
                            for r in rooms
                            if r.get("room_id") == finding.get("room_id")
                        ),
                        None,
                    ),
                    "photos": [
                        self._historical_photo(inspection_id, photo)
                        for photo in photos
                        if str(photo.get("finding_id", "")) == finding_id
                    ],
                }
            )
        return {
            "source_inspection_id": inspection_id,
            "system_type": _optional_text(context.get("system_type")),
            "project_id": _optional_text(context.get("project_id")),
            "inspector": _optional_text(context.get("inspector")),
            "inspection_date": _optional_text(context.get("inspection_date")),
            "source_kind": _optional_text(context.get("source_kind")) or "field",
            "previous_inspection_id": _optional_text(context.get("previous_inspection_id")),
            "saved_at": _optional_text(context.get("saved_at")),
            "snapshot_sha256": digest,
            "structure": {
                "units": _object_list(snapshot.get("units")),
                "rooms": rooms,
            },
            "historical_findings": historical_findings,
            "historical_measurements": _object_list(snapshot.get("measurements")),
            "historical_checkpoints": [
                item
                for item in _object_list(snapshot.get("checkpoints"))
                if item.get("status") == "fail"
            ],
            "historical_space_photos": [
                self._historical_photo(inspection_id, photo)
                for photo in photos
                if photo.get("space_id")
            ],
            "legacy": snapshot.get("legacy") if isinstance(snapshot.get("legacy"), dict) else None,
        }

    def _load_snapshot(self, inspection_id: str) -> tuple[dict[str, Any], str]:
        target = self._snapshot_root / f"{inspection_id}.json"
        canonical = target.read_text(encoding="utf-8").rstrip("\n")
        payload: Any = json.loads(canonical)
        if not isinstance(payload, dict):
            raise ValueError("OVK field snapshot must contain an object")
        return payload, sha256(canonical.encode()).hexdigest()

    def _historical_photo(self, inspection_id: str, photo: dict[str, Any]) -> dict[str, Any]:
        photo_id = str(photo.get("photo_id", ""))
        receipt_path = self._media_root / inspection_id / f"{photo_id}.json"
        try:
            receipt = _read_object(receipt_path)
        except FileNotFoundError:
            receipt = {}
        expected = str(photo.get("sha256", "")).lower()
        verified = bool(
            receipt
            and compare_digest(str(receipt.get("sha256", "")).lower(), expected)
            and str(receipt.get("inspection_id", "")) == inspection_id
            and str(receipt.get("photo_id", "")) == photo_id
        )
        return {
            **photo,
            "historical": True,
            "verified": verified,
            "media_id": receipt.get("media_id") if verified else None,
            "evidence_id": receipt.get("evidence_id") if verified else None,
            "content_url": (
                f"/api/ovk/field/media/{inspection_id}/{photo_id}/content" if verified else None
            ),
        }


def _read_object(path: Path) -> dict[str, Any]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object in {path.name}")
    return payload


def _object_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _validate_identifier(value: str) -> None:
    if not _SAFE_ID.fullmatch(value):
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"})
