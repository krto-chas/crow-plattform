from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from crow_ovk_export import (
    ExportSignatureError,
    intyg_pdf,
    protocol_pdf,
    sign_export_path,
    verify_export_signature,
)
from crow_ovk_intyg import OvkIntygRepository
from crow_ovk_workflow import OvkWorkflowRepository

_SIGNING_KEY_ENV = "CROW_EXPORT_SIGNING_KEY"
_DEFAULT_TTL_SECONDS = 3600
_MAX_TTL_SECONDS = 86400
_KINDS = ("protokoll", "intyg")


def ovk_export_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    workflow_repository = OvkWorkflowRepository(data_root)
    intyg_repository = OvkIntygRepository(data_root)

    @router.post(
        "/api/ovk/projects/{project_id}/export/{kind}/{document_id}/sign",
        response_model=None,
    )
    async def sign_export(
        project_id: str, kind: str, document_id: str, request: Request
    ) -> dict[str, Any]:
        secret = _signing_secret()
        _validate_kind(kind)
        _ensure_document_exists(
            workflow_repository, intyg_repository, project_id, kind, document_id
        )
        ttl = _DEFAULT_TTL_SECONDS
        body = await request.body()
        if body:
            payload: Any = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_EXPORT"})
            raw_ttl = payload.get("ttl_seconds", _DEFAULT_TTL_SECONDS)
            if not isinstance(raw_ttl, int) or raw_ttl < 1 or raw_ttl > _MAX_TTL_SECONDS:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "INVALID_OVK_EXPORT",
                        "message": f"ttl_seconds must be 1..{_MAX_TTL_SECONDS}",
                    },
                )
            ttl = raw_ttl
        expires = int(time.time()) + ttl
        path = _export_path(project_id, kind, document_id)
        signature = sign_export_path(secret, path, expires)
        return {
            "path": path,
            "url": f"{path}?expires={expires}&sig={signature}",
            "expires": expires,
            "algorithm": "hmac-sha256",
        }

    @router.get(
        "/api/ovk/export/{project_id}/{kind}/{document_id}.pdf",
        response_model=None,
    )
    def download_export(
        project_id: str,
        kind: str,
        document_id: str,
        expires: int = Query(...),
        sig: str = Query(...),
    ) -> Response:
        secret = _signing_secret()
        _validate_kind(kind)
        path = _export_path(project_id, kind, document_id)
        try:
            verify_export_signature(secret, path, expires, sig, now_epoch=int(time.time()))
        except ExportSignatureError as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "OVK_EXPORT_SIGNATURE_REJECTED", "message": str(exc)},
            ) from exc
        content = _render(workflow_repository, intyg_repository, project_id, kind, document_id)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (f'attachment; filename="ovk-{kind}-{document_id}.pdf"')
            },
        )

    return router


def _signing_secret() -> str:
    secret = os.environ.get(_SIGNING_KEY_ENV, "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "OVK_EXPORT_SIGNING_KEY_MISSING",
                "message": f"{_SIGNING_KEY_ENV} is not configured",
            },
        )
    return secret


def _validate_kind(kind: str) -> None:
    if kind not in _KINDS:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_OVK_EXPORT", "message": f"unknown kind {kind!r}"},
        )


def _export_path(project_id: str, kind: str, document_id: str) -> str:
    return f"/api/ovk/export/{project_id}/{kind}/{document_id}.pdf"


def _ensure_document_exists(
    workflow_repository: OvkWorkflowRepository,
    intyg_repository: OvkIntygRepository,
    project_id: str,
    kind: str,
    document_id: str,
) -> None:
    _render(workflow_repository, intyg_repository, project_id, kind, document_id)


def _render(
    workflow_repository: OvkWorkflowRepository,
    intyg_repository: OvkIntygRepository,
    project_id: str,
    kind: str,
    document_id: str,
) -> bytes:
    try:
        if kind == "protokoll":
            record = workflow_repository.load(project_id, document_id)
            if not record.protocol_ready:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "OVK_PROTOCOL_NOT_READY",
                        "unresolved_review_count": record.unresolved_review_count,
                    },
                )
            return protocol_pdf(record)
        intyg = intyg_repository.load(project_id, document_id)
        return intyg_pdf(intyg)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail={"code": "OVK_EXPORT_DOCUMENT_NOT_FOUND"}
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"}) from exc
