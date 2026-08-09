from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_field_media import ovk_field_media_router
from crow_ovk_module.ovk_field_surface import ovk_field_router


def _client(data_root: Path) -> TestClient:
    app = FastAPI()
    app.include_router(ovk_field_router(data_root))
    app.include_router(ovk_field_media_router(data_root))
    return TestClient(app)


def _payload(digest: str) -> dict[str, object]:
    return {
        "inspection_id": "ovk-1",
        "units": [
            {
                "unit_id": "unit-1",
                "number": "1203",
                "kind": "apartment",
            }
        ],
        "rooms": [
            {
                "room_id": "room-1",
                "unit_id": "unit-1",
                "name": "Badrum",
            }
        ],
        "findings": [
            {
                "finding_id": "finding-1",
                "unit_id": "unit-1",
                "room_id": "room-1",
                "defect_type": "contaminated_extract_terminal",
                "description": "Smutsigt frånluftsdon",
                "severity": "minor",
                "origin": "observed",
            }
        ],
        "photos": [
            {
                "photo_id": "photo-1",
                "unit_id": "unit-1",
                "unit_number": "1203",
                "defect_type": "contaminated_extract_terminal",
                "captured_at": "2026-08-09T09:00:00+02:00",
                "captured_by": "Inspector",
                "local_uri": "indexeddb:image.jpg",
                "sha256": digest,
                "mime_type": "image/jpeg",
                "room_id": "room-1",
                "finding_id": "finding-1",
                "sync_status": "local",
            }
        ],
    }


def test_media_upload_verifies_hash_and_binds_evidence(tmp_path: Path) -> None:
    client = _client(tmp_path)
    content = b"crow-ovk-photo-evidence"
    digest = sha256(content).hexdigest()
    payload = _payload(digest)
    snapshot = client.put("/api/ovk/field/sync/ovk-1", json=payload)
    assert snapshot.status_code == 200
    assert snapshot.json()["media_pending"] == 1

    first = client.put(
        "/api/ovk/field/media/ovk-1/photo-1",
        content=content,
        headers={"content-type": "image/jpeg"},
    )
    second = client.put(
        "/api/ovk/field/media/ovk-1/photo-1",
        content=content,
        headers={"content-type": "image/jpeg"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    receipt = first.json()
    assert receipt["media_id"] == f"sha256:{digest}"
    assert receipt["evidence_id"].startswith("ovk-photo:")
    assert receipt["sync_status"] == "synced"
    assert receipt["size_bytes"] == len(content)

    media_path = tmp_path / "ovk-field-media" / "ovk-1" / "photo-1.bin"
    assert media_path.read_bytes() == content
    receipt_path = tmp_path / "ovk-field-media" / "ovk-1" / "photo-1.json"
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["sha256"] == digest

    synced = client.get("/api/ovk/field/sync/ovk-1")
    assert synced.status_code == 200
    assert synced.json()["payload"]["photos"][0]["sync_status"] == "synced"

    downloaded = client.get("/api/ovk/field/media/ovk-1/photo-1/content")
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["etag"] == f'"{digest}"'
    assert downloaded.headers["x-crow-media-id"] == receipt["media_id"]
    assert downloaded.headers["x-crow-evidence-id"] == receipt["evidence_id"]


def test_media_upload_rejects_hash_mismatch(tmp_path: Path) -> None:
    client = _client(tmp_path)
    expected = sha256(b"expected").hexdigest()
    assert client.put("/api/ovk/field/sync/ovk-1", json=_payload(expected)).status_code == 200

    response = client.put(
        "/api/ovk/field/media/ovk-1/photo-1",
        content=b"different",
        headers={"content-type": "image/jpeg"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_MEDIA_HASH_MISMATCH"
    assert not (tmp_path / "ovk-field-media" / "ovk-1" / "photo-1.bin").exists()


def test_media_upload_requires_snapshot_binding(tmp_path: Path) -> None:
    response = _client(tmp_path).put(
        "/api/ovk/field/media/ovk-1/photo-1",
        content=b"photo",
        headers={"content-type": "image/jpeg"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_FIELD_SNAPSHOT_REQUIRED"


def test_media_upload_rejects_mime_mismatch(tmp_path: Path) -> None:
    client = _client(tmp_path)
    content = b"photo"
    digest = sha256(content).hexdigest()
    assert client.put("/api/ovk/field/sync/ovk-1", json=_payload(digest)).status_code == 200

    response = client.put(
        "/api/ovk/field/media/ovk-1/photo-1",
        content=content,
        headers={"content-type": "image/png"},
    )
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "OVK_MEDIA_TYPE_MISMATCH"
