from __future__ import annotations

import json
import re
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from crow_ovk_module.ovk_field_surface import _FieldSyncRepository
from crow_ovk_workflow import OvkWorkflowRepository

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_MAX_MEDIA_BYTES = 25 * 1024 * 1024


def ovk_field_media_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    repository = _FieldMediaRepository(data_root)

    async def _upload(
        inspection_id: str,
        photo_id: str,
        request: Request,
        store: _FieldMediaRepository,
    ) -> dict[str, Any]:
        _validate_identifier(inspection_id)
        _validate_identifier(photo_id)
        try:
            snapshot = store.load_snapshot(inspection_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "OVK_FIELD_SNAPSHOT_REQUIRED"},
            ) from exc

        expected = request.headers.get("X-OVK-Base-Revision")
        canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        current = sha256(canonical.encode("utf-8")).hexdigest()
        if expected is not None and expected != current:
            raise HTTPException(
                status_code=409,
                detail={"code": "OVK_FIELD_REVISION_CONFLICT", "current_revision": current},
            )
        photo = _find_photo(snapshot, photo_id)
        content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        expected_mime = str(photo.get("mime_type", "")).lower()
        if not content_type.startswith("image/") or content_type != expected_mime:
            raise HTTPException(
                status_code=415,
                detail={
                    "code": "OVK_MEDIA_TYPE_MISMATCH",
                    "expected": expected_mime,
                    "received": content_type,
                },
            )

        if store.project_id is not None and expected is None:
            raise HTTPException(status_code=428, detail={"code": "OVK_FIELD_REVISION_REQUIRED"})
        buffer = bytearray()
        async for chunk in request.stream():
            if len(buffer) + len(chunk) > _MAX_MEDIA_BYTES:
                raise HTTPException(status_code=413, detail={"code": "OVK_MEDIA_TOO_LARGE"})
            buffer.extend(chunk)
        content = bytes(buffer)
        if not content:
            raise HTTPException(status_code=422, detail={"code": "OVK_MEDIA_EMPTY"})
        if len(content) > _MAX_MEDIA_BYTES:
            raise HTTPException(status_code=413, detail={"code": "OVK_MEDIA_TOO_LARGE"})

        digest = sha256(content).hexdigest()
        expected_digest = str(photo.get("sha256", "")).lower()
        if not compare_digest(digest, expected_digest):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OVK_MEDIA_HASH_MISMATCH",
                    "expected_sha256": expected_digest,
                    "received_sha256": digest,
                },
            )

        receipt = store.save_media(
            inspection_id=inspection_id,
            photo_id=photo_id,
            mime_type=expected_mime,
            digest=digest,
            content=content,
        )
        revision = store.mark_photo_synced(inspection_id, snapshot, photo_id)
        return {**receipt, "sync_status": "synced", "snapshot_sha256": revision}

    @router.get(
        "/api/ovk/field/media/{inspection_id}/{photo_id}",
        response_model=None,
    )
    def media_receipt(inspection_id: str, photo_id: str) -> dict[str, Any]:
        _validate_identifier(inspection_id)
        _validate_identifier(photo_id)
        try:
            return repository.load_receipt(inspection_id, photo_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "OVK_MEDIA_NOT_FOUND"},
            ) from exc

    @router.get(
        "/api/ovk/field/media/{inspection_id}/{photo_id}/content",
        response_class=Response,
    )
    def media_content(inspection_id: str, photo_id: str) -> Response:
        _validate_identifier(inspection_id)
        _validate_identifier(photo_id)
        try:
            content, receipt = repository.load_media(inspection_id, photo_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "OVK_MEDIA_NOT_FOUND"},
            ) from exc
        return Response(
            content,
            media_type=str(receipt["mime_type"]),
            headers={
                "ETag": f'"{receipt["sha256"]}"',
                "X-Crow-Media-Id": str(receipt["media_id"]),
                "X-Crow-Evidence-Id": str(receipt["evidence_id"]),
            },
        )

    @router.put("/api/ovk/field/media/{inspection_id}/{photo_id}", response_model=None)
    async def upload_media(inspection_id: str, photo_id: str, request: Request) -> dict[str, Any]:
        return await _upload(inspection_id, photo_id, request, repository)

    def _scoped(project_id: str, inspection_id: str) -> _FieldMediaRepository:
        _validate_identifier(project_id)
        _validate_identifier(inspection_id)
        try:
            record = OvkWorkflowRepository(data_root).load(project_id, inspection_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "OVK_INSPECTION_NOT_FOUND"}
            ) from exc
        if record.inspection.ovk_object.project_id != project_id:
            raise HTTPException(status_code=409, detail={"code": "OVK_FIELD_PROJECT_CONFLICT"})
        return _FieldMediaRepository(data_root, project_id=project_id)

    @router.put("/api/ovk/projects/{project_id}/field/{inspection_id}/media/{photo_id}")
    async def upload_project_media(
        project_id: str, inspection_id: str, photo_id: str, request: Request
    ) -> dict[str, Any]:
        return await _upload(inspection_id, photo_id, request, _scoped(project_id, inspection_id))

    @router.get("/api/ovk/projects/{project_id}/field/{inspection_id}/media/{photo_id}")
    def project_receipt(project_id: str, inspection_id: str, photo_id: str) -> dict[str, Any]:
        try:
            return _scoped(project_id, inspection_id).load_receipt(inspection_id, photo_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail={"code": "OVK_MEDIA_NOT_FOUND"}) from exc

    @router.get("/api/ovk/projects/{project_id}/field/{inspection_id}/media/{photo_id}/content")
    def project_content(project_id: str, inspection_id: str, photo_id: str) -> Response:
        try:
            store = _scoped(project_id, inspection_id)
            content, receipt = store.load_media(inspection_id, photo_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail={"code": "OVK_MEDIA_NOT_FOUND"}) from exc
        return Response(
            content,
            media_type=str(receipt["mime_type"]),
            headers={
                "ETag": f'"{receipt["sha256"]}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": "attachment",
            },
        )

    return router


def _validate_identifier(value: str) -> None:
    if value in {".", ".."} or not _SAFE_ID.fullmatch(value):
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"})


def _find_photo(snapshot: dict[str, Any], photo_id: str) -> dict[str, Any]:
    photos = snapshot.get("photos")
    if not isinstance(photos, list):
        raise HTTPException(status_code=409, detail={"code": "OVK_FIELD_SNAPSHOT_INVALID"})
    for item in photos:
        if isinstance(item, dict) and str(item.get("photo_id", "")) == photo_id:
            return item
    raise HTTPException(status_code=404, detail={"code": "OVK_PHOTO_NOT_IN_SNAPSHOT"})


class _FieldMediaRepository:
    def __init__(self, data_root: Path, *, project_id: str | None = None) -> None:
        self.project_id = project_id
        self._sync = _FieldSyncRepository(data_root, project_id=project_id)
        self._scoped_root: Path | None = None
        if project_id is not None:
            _validate_identifier(project_id)
            self._scoped_root = data_root / "projects" / project_id / "ovk-field"
        self._media_root = data_root / "ovk-field-media"

    def load_snapshot(self, inspection_id: str) -> dict[str, Any]:
        return self._sync.load(inspection_id)[0]

    def save_media(
        self,
        *,
        inspection_id: str,
        photo_id: str,
        mime_type: str,
        digest: str,
        content: bytes,
    ) -> dict[str, Any]:
        directory = self._directory(inspection_id, photo_id, digest)
        directory.mkdir(parents=True, exist_ok=True)
        media_id = f"sha256:{digest}"
        identity = f"{inspection_id}\0{photo_id}\0{digest}"
        if self.project_id is not None:
            identity = f"{self.project_id}\0{identity}"
        evidence_digest = sha256(identity.encode()).hexdigest()
        receipt: dict[str, Any] = {
            "inspection_id": inspection_id,
            "photo_id": photo_id,
            "media_id": media_id,
            "evidence_id": f"ovk-photo:{evidence_digest}",
            "sha256": digest,
            "mime_type": mime_type,
            "size_bytes": len(content),
        }
        if self.project_id is not None:
            receipt["project_id"] = self.project_id
            self._publish_immutable(directory / f"{photo_id}.bin", content)
            encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
            self._publish_immutable(directory / f"{photo_id}.json", encoded)
            return receipt
        media_target = directory / f"{photo_id}.bin"
        media_temporary = directory / f".{photo_id}.bin.tmp"
        media_temporary.write_bytes(content)
        media_temporary.replace(media_target)
        self._write_json(directory / f"{photo_id}.json", receipt)
        return receipt

    def _directory(self, inspection_id: str, photo_id: str, digest: str) -> Path:
        _validate_identifier(inspection_id)
        _validate_identifier(photo_id)
        if self._scoped_root is not None:
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("invalid media digest")
            return self._scoped_root / inspection_id / "media" / photo_id / digest
        return self._media_root / inspection_id

    @staticmethod
    def _publish_immutable(target: Path, content: bytes) -> None:
        with NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        try:
            try:
                target.hardlink_to(temporary)
            except FileExistsError:
                if target.read_bytes() != content:
                    raise HTTPException(status_code=409, detail={"code": "OVK_MEDIA_CONFLICT"})
        finally:
            temporary.unlink(missing_ok=True)

    def load_receipt(self, inspection_id: str, photo_id: str) -> dict[str, Any]:
        digest = ""
        if self.project_id is not None:
            photo = _find_photo(self.load_snapshot(inspection_id), photo_id)
            if photo.get("sync_status") != "synced":
                raise FileNotFoundError(photo_id)
            digest = str(photo.get("sha256", "")).lower()
        target = self._directory(inspection_id, photo_id, digest) / f"{photo_id}.json"
        payload: Any = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("OVK media receipt must contain an object")
        if self.project_id is not None and (
            payload.get("project_id") != self.project_id
            or payload.get("inspection_id") != inspection_id
            or payload.get("photo_id") != photo_id
            or payload.get("sha256") != digest
        ):
            raise ValueError("OVK media receipt identity mismatch")
        return payload

    def load_media(self, inspection_id: str, photo_id: str) -> tuple[bytes, dict[str, Any]]:
        receipt = self.load_receipt(inspection_id, photo_id)
        directory = self._directory(inspection_id, photo_id, str(receipt.get("sha256", "")))
        content = (directory / f"{photo_id}.bin").read_bytes()
        digest = sha256(content).hexdigest()
        if not compare_digest(digest, str(receipt.get("sha256", ""))):
            raise ValueError("Stored OVK media failed checksum verification")
        return content, receipt

    def mark_photo_synced(
        self,
        inspection_id: str,
        snapshot: dict[str, Any],
        photo_id: str,
    ) -> str:
        canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        expected = sha256(canonical.encode("utf-8")).hexdigest()
        photo = _find_photo(snapshot, photo_id)
        photo["sync_status"] = "synced"
        return self._sync.save(inspection_id, snapshot, expected)

    @staticmethod
    def _write_json(target: Path, payload: dict[str, Any]) -> None:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        temporary.write_text(canonical + "\n", encoding="utf-8")
        temporary.replace(target)
