from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_field_surface import ovk_field_router


def _client(data_root: Path) -> TestClient:
    app = FastAPI()
    app.include_router(ovk_field_router(data_root))
    return TestClient(app)


def _field_payload() -> dict[str, object]:
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
                "captured_at": "2026-08-09T00:00:00+02:00",
                "captured_by": "Inspector",
                "local_uri": "indexeddb:image.jpg",
                "sha256": "a" * 64,
                "mime_type": "image/jpeg",
                "room_id": "room-1",
                "finding_id": "finding-1",
                "sync_status": "local",
            }
        ],
    }


def test_field_page_exposes_offline_app_shell(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/ovk/falt")
    assert response.status_code == 200
    assert "Crow OVK · Fält" in response.text
    assert "capture=\"environment\"" in response.text
    assert "/ovk/falt/app.js" in response.text

    app = client.get("/ovk/falt/app.js")
    assert app.status_code == 200
    assert "indexedDB.open" in app.text
    assert "serviceWorker.register" in app.text
    assert "sync_status:'local'" in app.text

    worker = client.get("/ovk/falt/sw.js")
    assert worker.status_code == 200
    assert worker.headers["service-worker-allowed"] == "/ovk/"
    assert "crow-ovk-field-shell-v1" in worker.text


def test_defect_types_are_exposed(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/ovk/field/defect-types")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["defect_types"]}
    assert "contaminated_extract_terminal" in ids


def test_field_payload_validates_photo_unit_and_defect(tmp_path: Path) -> None:
    response = _client(tmp_path).post("/api/ovk/field/validate", json=_field_payload())
    assert response.status_code == 200
    assert response.json() == {
        "inspection_id": "ovk-1",
        "units": 1,
        "rooms": 1,
        "findings": 1,
        "photos": 1,
        "valid": True,
    }


def test_field_sync_persists_canonical_snapshot_with_stable_receipt(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = _field_payload()

    first = client.put("/api/ovk/field/sync/ovk-1", json=payload)
    second = client.put("/api/ovk/field/sync/ovk-1", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["snapshot_sha256"] == second.json()["snapshot_sha256"]
    assert first.json()["media_pending"] == 1
    assert first.json()["synced"] is True

    snapshot = tmp_path / "ovk-field-sync" / "ovk-1.json"
    assert snapshot.is_file()
    stored = json.loads(snapshot.read_text(encoding="utf-8"))
    assert stored["inspection_id"] == "ovk-1"
    assert stored["photos"][0]["sync_status"] == "local"

    loaded = client.get("/api/ovk/field/sync/ovk-1")
    assert loaded.status_code == 200
    assert loaded.json()["snapshot_sha256"] == first.json()["snapshot_sha256"]
    assert loaded.json()["payload"] == stored


def test_field_sync_rejects_identifier_mismatch(tmp_path: Path) -> None:
    response = _client(tmp_path).put(
        "/api/ovk/field/sync/ovk-2",
        json=_field_payload(),
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_FIELD_INSPECTION_MISMATCH"


def test_field_payload_rejects_wrong_photo_unit_number(tmp_path: Path) -> None:
    payload = {
        "inspection_id": "ovk-1",
        "units": [{"unit_id": "unit-1", "number": "1203"}],
        "rooms": [],
        "findings": [],
        "photos": [
            {
                "photo_id": "photo-1",
                "unit_id": "unit-1",
                "unit_number": "1303",
                "defect_type": "contaminated_extract_terminal",
                "captured_at": "2026-08-09T00:00:00+02:00",
                "captured_by": "Inspector",
                "local_uri": "indexeddb:image.jpg",
                "sha256": "b" * 64,
                "mime_type": "image/jpeg",
            }
        ],
    }
    response = _client(tmp_path).post("/api/ovk/field/validate", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_OVK_FIELD_DATA"
