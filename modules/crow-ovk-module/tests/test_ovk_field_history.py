from __future__ import annotations

from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk import OvkObject, VentilationSystemRef
from crow_ovk_module.ovk_field_history import ovk_field_history_router
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
    app.include_router(ovk_field_history_router(data_root))
    return TestClient(app)


def _payload(content: bytes) -> dict[str, object]:
    return {
        "inspection_id": "ovk-2025",
        "units": [
            {
                "unit_id": "unit-old",
                "number": "1203",
                "kind": "apartment",
                "label": "",
            }
        ],
        "rooms": [{"room_id": "room-old", "unit_id": "unit-old", "name": "Badrum"}],
        "findings": [
            {
                "finding_id": "finding-old",
                "unit_id": "unit-old",
                "room_id": "room-old",
                "defect_type": "contaminated_extract_terminal",
                "description": "Smutsigt frånluftsdon",
                "severity": "minor",
                "system_id": "F1",
                "rule_refs": [],
                "origin": "observed",
            }
        ],
        "photos": [
            {
                "photo_id": "photo-old",
                "unit_id": "unit-old",
                "unit_number": "1203",
                "defect_type": "contaminated_extract_terminal",
                "captured_at": "2025-08-09T09:00:00+02:00",
                "captured_by": "Inspector",
                "local_uri": "indexeddb:old.jpg",
                "sha256": sha256(content).hexdigest(),
                "mime_type": "image/jpeg",
                "room_id": "room-old",
                "finding_id": "finding-old",
                "system_id": "F1",
                "description": "Smutsigt frånluftsdon",
                "rule_refs": [],
                "sync_status": "local",
            }
        ],
    }


def _seed_previous(client: TestClient, content: bytes) -> dict[str, object]:
    context = client.put(
        "/api/ovk/field/context/ovk-2025",
        json={"project_id": "property-a", "inspector": "Inspector"},
    )
    snapshot = client.put("/api/ovk/field/sync/ovk-2025", json=_payload(content))
    media = client.put(
        "/api/ovk/field/media/ovk-2025/photo-old",
        content=content,
        headers={"content-type": "image/jpeg"},
    )
    assert context.status_code == 200
    assert snapshot.status_code == 200
    assert media.status_code == 200
    return cast(dict[str, object], media.json())


def test_history_lists_server_inspections_by_project(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _seed_previous(client, b"old-photo")

    response = client.get("/api/ovk/field/history", params={"project_id": "property-a"})

    assert response.status_code == 200
    items = response.json()["inspections"]
    assert len(items) == 1
    assert items[0]["inspection_id"] == "ovk-2025"
    assert items[0]["project_id"] == "property-a"
    assert items[0]["counts"] == {"units": 1, "rooms": 1, "findings": 1, "photos": 1}


def test_restore_projection_keeps_old_findings_as_history(tmp_path: Path) -> None:
    client = _client(tmp_path)
    media = _seed_previous(client, b"old-photo")

    response = client.get("/api/ovk/field/history/ovk-2025")

    assert response.status_code == 200
    data = response.json()
    assert data["source_inspection_id"] == "ovk-2025"
    assert data["project_id"] == "property-a"
    assert data["structure"]["units"][0]["number"] == "1203"
    assert data["structure"]["rooms"][0]["name"] == "Badrum"
    historical = data["historical_findings"][0]
    assert historical["source_inspection_id"] == "ovk-2025"
    assert historical["finding_id"] == "finding-old"
    photo = historical["photos"][0]
    assert photo["historical"] is True
    assert photo["verified"] is True
    assert photo["evidence_id"] == media["evidence_id"]
    assert photo["content_url"] == "/api/ovk/field/media/ovk-2025/photo-old/content"


def test_new_context_can_reference_previous_inspection(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _seed_previous(client, b"old-photo")

    response = client.put(
        "/api/ovk/field/context/ovk-2028",
        json={
            "project_id": "property-a",
            "inspector": "Inspector 2",
            "previous_inspection_id": "ovk-2025",
        },
    )

    assert response.status_code == 200
    assert response.json()["previous_inspection_id"] == "ovk-2025"
    assert response.json()["saved_at"]


def test_context_rejects_self_predecessor(tmp_path: Path) -> None:
    response = _client(tmp_path).put(
        "/api/ovk/field/context/ovk-2028",
        json={
            "project_id": "property-a",
            "inspector": "Inspector",
            "previous_inspection_id": "ovk-2028",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_FIELD_SELF_PREDECESSOR"


def test_scoped_history_never_falls_back_to_global_data(tmp_path: Path) -> None:
    client = _client(tmp_path)
    workflows = OvkWorkflowRepository(tmp_path)
    _seed_previous(client, b"legacy-photo")
    for project_id in ("property-a", "property-b"):
        for inspection_id, year, previous in (
            ("ovk-2025", 2025, None),
            ("ovk-2028", 2028, "ovk-2025"),
        ):
            workflows.save(
                build_record(
                    inspection_id=inspection_id,
                    ovk_object=OvkObject("object-1", project_id, "building-1", "Building"),
                    systems=(VentilationSystemRef("F1", "F", "System F1"),),
                    checkpoints=(),
                    findings=(),
                    actions=(),
                    planning=InspectionPlanning(
                        inspector_id="inspector-1",
                        planned_date=date(year, 8, 9),
                        inspection_type="aterkommande",
                        previous_inspection_id=previous,
                    ),
                )
            )
    first = "/api/ovk/projects/property-a/field"
    second = "/api/ovk/projects/property-b/field"
    assert client.get(f"{first}/ovk-2028/history").status_code == 404
    for root, content in ((first, b"first"), (second, b"second")):
        source = f"{root}/ovk-2025"
        assert client.put(f"{source}/context", json={"system_type": "F"}).status_code == 200
        saved = client.put(f"{source}/sync", json=_payload(content))
        assert saved.status_code == 200, saved.text
        uploaded = client.put(
            f"{source}/media/photo-old",
            content=content,
            headers={
                "Content-Type": "image/jpeg",
                "X-OVK-Base-Revision": saved.json()["snapshot_sha256"],
            },
        )
        assert uploaded.status_code == 200, uploaded.text
        history = client.get(f"{root}/ovk-2028/history")
        assert history.status_code == 200, history.text
        photo = history.json()["historical_findings"][0]["photos"][0]
        assert photo["verified"] is True
        assert photo["content_url"] == f"{source}/media/photo-old/content"
        assert client.get(photo["content_url"]).content == content
        context = client.put(f"{root}/ovk-2028/context", json={"system_type": "F"})
        assert context.status_code == 200
        payload = {
            **_payload(content),
            "inspection_id": "ovk-2028",
            "photos": [],
            "finding_followups": [
                {
                    "source_inspection_id": "ovk-2025",
                    "source_finding_id": "finding-old",
                    "unit_id": "unit-old",
                    "status": "resolved",
                }
            ],
        }
        result = client.put(f"{root}/ovk-2028/sync", json=payload)
        assert result.status_code == 200, result.text
    assert client.get(f"{first}/ovk-2025/media/photo-old/content").content == b"first"
    assert client.get(f"{second}/ovk-2025/media/photo-old/content").content == b"second"
