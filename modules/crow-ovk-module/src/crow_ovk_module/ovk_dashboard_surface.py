from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path
from typing import Any

from crow_ovk_legacy import preview_legacy_file
from crow_ovk_legacy.models import LegacyImportPreview
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

_SAFE_PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,119}$")
_SAFE_CHECKSUM = re.compile(r"^[0-9a-f]{64}$")


def ovk_dashboard_router(data_root: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/ovk", response_class=HTMLResponse)
    def dashboard_page() -> str:
        return (
            resources.files("crow_ovk_module")
            .joinpath("assets", "dashboard.html")
            .read_text(encoding="utf-8")
        )

    @router.get(
        "/api/ovk/projects/{project_id}/legacy-assets/{checksum}/preview",
        response_model=None,
    )
    def preview_project_legacy_asset(project_id: str, checksum: str) -> dict[str, Any]:
        safe_project = _project_id(project_id)
        safe_checksum = checksum.strip().lower()
        if not _SAFE_CHECKSUM.fullmatch(safe_checksum):
            raise HTTPException(status_code=400, detail={"code": "INVALID_IMPORT_CHECKSUM"})

        manifest_path = data_root / "projects" / safe_project / "imports" / f"{safe_checksum}.json"
        if not manifest_path.is_file():
            raise HTTPException(status_code=404, detail={"code": "PROJECT_IMPORT_NOT_FOUND"})
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail={"code": "PROJECT_IMPORT_INVALID"}) from exc

        filename = Path(str(manifest.get("filename", ""))).name
        if not filename:
            raise HTTPException(status_code=422, detail={"code": "PROJECT_IMPORT_FILENAME_MISSING"})
        source_path = data_root / "uploads" / safe_project / filename
        if not source_path.is_file():
            raise HTTPException(status_code=404, detail={"code": "PROJECT_IMPORT_SOURCE_MISSING"})

        try:
            preview = preview_legacy_file(safe_project, filename, source_path.read_bytes())
        except ValueError as exc:
            raise HTTPException(
                status_code=415,
                detail={"code": "UNSUPPORTED_LEGACY_OVK_FILE", "message": str(exc)},
            ) from exc
        if preview.source_sha256 != safe_checksum:
            raise HTTPException(
                status_code=409, detail={"code": "PROJECT_IMPORT_CHECKSUM_MISMATCH"}
            )
        return _preview_payload(preview)

    return router


def _project_id(value: str) -> str:
    normalized = value.strip().lower()
    if not _SAFE_PROJECT_ID.fullmatch(normalized):
        raise HTTPException(status_code=400, detail={"code": "INVALID_OVK_PROJECT"})
    return normalized


def _preview_payload(preview: LegacyImportPreview) -> dict[str, Any]:
    return {
        "project_id": preview.project_id,
        "filename": preview.filename,
        "kind": preview.kind.value,
        "source_sha256": preview.source_sha256,
        "ready_for_commit": preview.ready_for_commit,
        "facts": [
            {
                "field": fact.field,
                "value": fact.value,
                "confidence": fact.confidence,
                "status": fact.status.value,
                "source": {
                    "source_id": fact.source.source_id,
                    "filename": fact.source.filename,
                    "kind": fact.source.kind.value,
                    "locator": fact.source.locator,
                    "sha256": fact.source.sha256,
                },
            }
            for fact in preview.facts
        ],
        "review": [
            {
                "reason": item.reason,
                "source_text": item.source_text,
                "source": {
                    "source_id": item.source.source_id,
                    "filename": item.source.filename,
                    "kind": item.source.kind.value,
                    "locator": item.source.locator,
                    "sha256": item.source.sha256,
                },
            }
            for item in preview.review
        ],
    }
