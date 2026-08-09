# ruff: noqa: B008
from __future__ import annotations

from pathlib import Path
from typing import Any

from crow_ovk_legacy import (
    LegacyHistoryCommitRepository,
    historical_commit_from_payload,
    preview_legacy_file,
)
from fastapi import APIRouter, File, Form, HTTPException, UploadFile


def ovk_legacy_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    repository = LegacyHistoryCommitRepository(data_root)

    @router.post("/api/ovk/legacy/preview", response_model=None)
    async def preview_legacy(
        project_id: str = Form(...),
        file: UploadFile = File(...),
    ) -> dict[str, Any]:
        filename = file.filename or "legacy-ovk"
        content = await file.read()
        if not content:
            raise HTTPException(status_code=422, detail={"code": "EMPTY_LEGACY_OVK_FILE"})
        try:
            preview = preview_legacy_file(project_id, filename, content)
        except ValueError as exc:
            raise HTTPException(
                status_code=415,
                detail={"code": "UNSUPPORTED_LEGACY_OVK_FILE", "message": str(exc)},
            ) from exc
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

    @router.post("/api/ovk/legacy/commit", response_model=None)
    def commit_legacy(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            historical = historical_commit_from_payload(payload)
            digest = repository.commit(historical)
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_LEGACY_OVK_COMMIT", "message": str(exc)},
            ) from exc
        return {
            "inspection_id": historical.inspection_id,
            "project_id": historical.project_id,
            "inspection_date": historical.inspection_date,
            "source_sha256": historical.source_sha256,
            "snapshot_sha256": digest,
            "committed": True,
        }

    return router
