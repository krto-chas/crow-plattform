from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_field_media import ovk_field_media_router
from crow_ovk_module.ovk_field_surface import ovk_field_router
from crow_ovk_module.ovk_field_workbench import ovk_field_workbench_router


def _client(data_root: Path) -> TestClient:
    app = FastAPI()
    app.include_router(ovk_field_router(data_root))
    app.include_router(ovk_field_media_router(data_root))
    app.include_router(ovk_field_workbench_router(data_root))
    return TestClient(app)


def _payload(content: bytes) -> dict[str, object]:
    return {
        "inspection_id": "ovk-78",
        "units": [
            {"unit_id": "unit-1", "number": "1203", "kind": "apartment", "label": ""}
        ],
        "rooms": [{"room_id": "room-1", "unit_id": "unit-1", "name": "Badrum"}],
        "findings": [
            {
                "finding_id": "finding-1",
                "unit_id": "unit-1",
                "room_id": "room-1",
                "defect_type": "contaminated_extract_terminal",
                "description": "Smutsigt frånluftsdon",
                "severity": "minor",
                "system_id": "FTX01",
                "rule_refs": ["PBL-OVK"],
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
                "sha256": sha256(content).hexdigest(),
                "mime_type": "image/jpeg",
                "room_id": "room-1",
                "finding_id": "finding-1",
                "system_id": "FTX01",
                "description": "Smutsigt frånluftsdon",
                "rule_refs": ["PBL-OVK"],
                "sync_status": "local",
            }
        ],
    }


def test_field_roundtrip_projects_verified_evidence_into_workbench(tmp_path: Path) -> None:
    client = _client(tmp_path)
    content = b"verified-ovk-photo"

    context = client.put(
        "/api/ovk/field/context/ovk-78",
        json={"project_id": "project-1", "inspector": "Inspector"},
    )
    snapshot = client.put("/api/ovk/field/sync/ovk-78", json=_payload(content))
    media = client.put(
        "/api/ovk/field/media/ovk-78/photo-1",
        content=content,
        headers={"content-type": "image/jpeg"},
    )

    assert context.status_code == 200
    assert snapshot.status_code == 200
    assert media.status_code == 200

    response = client.get("/api/ovk/field/workbench/ovk-78")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == "project-1"
    assert data["inspector"] == "Inspector"
    assert data["counts"] == {
        "units": 1,
        "rooms": 1,
        "findings": 1,
        "photos": 1,
        "verified_photos": 1,
    }
    finding = data["units"][0]["findings"][0]
    assert finding["room_name"] == "Badrum"
    assert finding["rule_refs"] == ["PBL-OVK"]
    photo = finding["photos"][0]
    assert photo["verified"] is True
    assert photo["media_id"] == media.json()["media_id"]
    assert photo["evidence_id"] == media.json()["evidence_id"]
    assert photo["content_url"] == "/api/ovk/field/media/ovk-78/photo-1/content"


def test_field_roundtrip_does_not_claim_unuploaded_photo_is_verified(tmp_path: Path) -> None:
    client = _client(tmp_path)
    content = b"local-only-photo"
    assert client.put("/api/ovk/field/sync/ovk-78", json=_payload(content)).status_code == 200

    response = client.get("/api/ovk/field/workbench/ovk-78")
    assert response.status_code == 200
    data = response.json()
    assert data["counts"]["verified_photos"] == 0
    photo = data["units"][0]["findings"][0]["photos"][0]
    assert photo["verified"] is False
    assert photo["evidence_id"] is None
    assert photo["content_url"] is None


def test_field_context_requires_project_and_inspector(tmp_path: Path) -> None:
    response = _client(tmp_path).put(
        "/api/ovk/field/context/ovk-78",
        json={"project_id": "project-1"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_OVK_FIELD_CONTEXT"
