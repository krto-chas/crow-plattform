from __future__ import annotations

import json
import re
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_MAX_MEDIA_BYTES = 25 * 1024 * 1024


def ovk_field_media_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    repository = _FieldMediaRepository(data_root)

    @router.put(
        "/api/ovk/field/media/{inspection_id}/{photo_id}",
        response_model=None,
    )
    async def upload_media(
        inspection_id: str,
        photo_id: str,
        request: Request,
    ) -> dict[str, Any]:
        _validate_identifier(inspection_id)
        _validate_identifier(photo_id)
        try:
            snapshot = repository.load_snapshot(inspection_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "OVK_FIELD_SNAPSHOT_REQUIRED"},
            ) from exc

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

        content = await request.body()
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

        receipt = repository.save_media(
            inspection_id=inspection_id,
            photo_id=photo_id,
            mime_type=expected_mime,
            digest=digest,
            content=content,
        )
        repository.mark_photo_synced(inspection_id, snapshot, photo_id)
        return {**receipt, "sync_status": "synced"}

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

    return router


def _validate_identifier(value: str) -> None:
    if not _SAFE_ID.fullmatch(value):
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
    def __init__(self, data_root: Path) -> None:
        self._snapshot_root = data_root / "ovk-field-sync"
        self._media_root = data_root / "ovk-field-media"

    def load_snapshot(self, inspection_id: str) -> dict[str, Any]:
        target = self._snapshot_root / f"{inspection_id}.json"
        payload: Any = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("OVK field snapshot must contain an object")
        return payload

    def save_media(
        self,
        *,
        inspection_id: str,
        photo_id: str,
        mime_type: str,
        digest: str,
        content: bytes,
    ) -> dict[str, Any]:
        directory = self._media_root / inspection_id
        directory.mkdir(parents=True, exist_ok=True)
        media_id = f"sha256:{digest}"
        evidence_digest = sha256(f"{inspection_id}\0{photo_id}\0{digest}".encode()).hexdigest()
        receipt: dict[str, Any] = {
            "inspection_id": inspection_id,
            "photo_id": photo_id,
            "media_id": media_id,
            "evidence_id": f"ovk-photo:{evidence_digest}",
            "sha256": digest,
            "mime_type": mime_type,
            "size_bytes": len(content),
        }
        media_target = directory / f"{photo_id}.bin"
        media_temporary = directory / f".{photo_id}.bin.tmp"
        media_temporary.write_bytes(content)
        media_temporary.replace(media_target)
        self._write_json(directory / f"{photo_id}.json", receipt)
        return receipt

    def load_receipt(self, inspection_id: str, photo_id: str) -> dict[str, Any]:
        target = self._media_root / inspection_id / f"{photo_id}.json"
        payload: Any = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("OVK media receipt must contain an object")
        return payload

    def load_media(self, inspection_id: str, photo_id: str) -> tuple[bytes, dict[str, Any]]:
        directory = self._media_root / inspection_id
        receipt = self.load_receipt(inspection_id, photo_id)
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
    ) -> None:
        photo = _find_photo(snapshot, photo_id)
        photo["sync_status"] = "synced"
        target = self._snapshot_root / f"{inspection_id}.json"
        self._write_json(target, snapshot)

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
