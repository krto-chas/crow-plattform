from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_workbench.ovk_field_surface import ovk_field_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(ovk_field_router())
    return TestClient(app)


def test_field_page_is_mobile_surface() -> None:
    response = _client().get("/ovk/falt")
    assert response.status_code == 200
    assert "Crow OVK · Fält" in response.text
    assert "capture=\"environment\"" in response.text


def test_defect_types_are_exposed() -> None:
    response = _client().get("/api/ovk/field/defect-types")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["defect_types"]}
    assert "contaminated_extract_terminal" in ids


def test_field_payload_validates_photo_unit_and_defect() -> None:
    payload = {
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
                "local_uri": "browser-session:image.jpg",
                "sha256": "a" * 64,
                "mime_type": "image/jpeg",
                "room_id": "room-1",
                "finding_id": "finding-1",
                "sync_status": "local",
            }
        ],
    }
    response = _client().post("/api/ovk/field/validate", json=payload)
    assert response.status_code == 200
    assert response.json() == {
        "inspection_id": "ovk-1",
        "units": 1,
        "rooms": 1,
        "findings": 1,
        "photos": 1,
        "valid": True,
    }


def test_field_payload_rejects_wrong_photo_unit_number() -> None:
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
                "local_uri": "browser-session:image.jpg",
                "sha256": "b" * 64,
                "mime_type": "image/jpeg",
            }
        ],
    }
    response = _client().post("/api/ovk/field/validate", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_OVK_FIELD_DATA"
