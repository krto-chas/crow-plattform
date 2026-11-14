from __future__ import annotations

from datetime import date
from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk import OvkObject, VentilationSystemRef
from crow_ovk_module.ovk_field_media import ovk_field_media_router
from crow_ovk_module.ovk_field_surface import ovk_field_router
from crow_ovk_module.ovk_field_workbench import ovk_field_workbench_router
from crow_ovk_workflow import OvkWorkflowRepository, build_record
from crow_ovk_workflow.models import InspectionPlanning


def _client(data_root: Path) -> TestClient:
    app = FastAPI()
    app.include_router(ovk_field_router(data_root))
    app.include_router(ovk_field_media_router(data_root))
    app.include_router(ovk_field_workbench_router(data_root))
    return TestClient(app)


def _payload(content: bytes) -> dict[str, object]:
    return {
        "inspection_id": "ovk-78",
        "units": [{"unit_id": "unit-1", "number": "1203", "kind": "apartment", "label": ""}],
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
                "rule_refs": [],
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
                "rule_refs": [],
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
    assert finding["rule_refs"] == []
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


def test_field_context_cannot_be_reassigned_to_another_project(tmp_path: Path) -> None:
    client = _client(tmp_path)
    url = "/api/ovk/field/context/ovk-78"
    original = {"project_id": "project-1", "inspector": "Inspector"}
    assert client.put(url, json=original).status_code == 200
    assert client.put("/api/ovk/field/sync/ovk-78", json=_payload(b"photo")).status_code == 200
    conflict = client.put(url, json={**original, "project_id": "project-2"})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "OVK_FIELD_PROJECT_CONFLICT"
    assert client.put(url, json={**original, "inspector": "Updated"}).status_code == 200
    result = client.get("/api/ovk/field/workbench/ovk-78")
    assert result.status_code == 200
    assert result.json()["project_id"] == "project-1"
    assert result.json()["inspector"] == "Updated"


def test_project_context_is_independent_and_bound_to_planning(tmp_path: Path) -> None:
    client = _client(tmp_path)
    workflows = OvkWorkflowRepository(tmp_path)
    for project_id in ("p1", "p2"):
        workflows.save(
            build_record(
                inspection_id="ovk-78",
                ovk_object=OvkObject("object-1", project_id, "building-1", "Building"),
                systems=(VentilationSystemRef("F01", "F", "System F01"),),
                checkpoints=(),
                findings=(),
                actions=(),
                planning=InspectionPlanning(
                    inspector_id=f"inspector-{project_id}",
                    planned_date=date(2026, 11, 14),
                    inspection_type="aterkommande",
                ),
            )
        )
    first = "/api/ovk/projects/p1/field/ovk-78/context"
    second = "/api/ovk/projects/p2/field/ovk-78/context"
    payload = {"system_type": "F"}
    saved = client.put(first, json=payload)
    assert saved.status_code == 200, saved.text
    assert client.get(second).status_code == 404
    assert client.put(second, json=payload).status_code == 200
    assert client.get(first).json()["inspector_id"] == "inspector-p1"
    assert client.get(second).json()["inspector_id"] == "inspector-p2"
    for invalid in (
        {"project_id": "p2"},
        {"inspection_id": "other"},
        {"inspector_id": "inspector-p2"},
        {"previous_inspection_id": "other"},
    ):
        assert client.put(first, json={**payload, **invalid}).status_code == 409
    assert client.put(first, json={"system_type": "FTX"}).status_code == 422
    assert client.get(first).json() == saved.json()
    assert client.get("/api/ovk/projects/p3/field/ovk-78/context").status_code == 404
    assert (tmp_path / "projects/p1/ovk-field/ovk-78/context.json").is_file()
    assert (tmp_path / "projects/p2/ovk-field/ovk-78/context.json").is_file()
    assert not (tmp_path / "ovk-field-context/ovk-78.json").exists()
