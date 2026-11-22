from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from crow_ovk import (
    CheckStatus,
    OvkCheckpoint,
    OvkObject,
    VentilationSystemRef,
)
from crow_ovk_workflow import (
    AggregatCoverage,
    AggregatStatus,
    BekraftelseRoll,
    InspectionCoverage,
    OvkReviewDecision,
    OvkWorkflowRecord,
    OvkWorkflowRepository,
    ReviewStatus,
    SystemForteckningBekraftelse,
    build_record,
    protocol_html,
)
from crow_workbench.shell import create_app


def _record(*, review_status: ReviewStatus = ReviewStatus.ACCEPTED) -> OvkWorkflowRecord:
    return build_record(
        inspection_id="ovk-001",
        ovk_object=OvkObject(
            object_id="object-1",
            project_id="p1",
            building_id="building-1",
            name="Testobjekt",
        ),
        systems=(VentilationSystemRef("FTX01", "FTX", "System FTX01"),),
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="cp1",
                label="Drift och funktion",
                status=CheckStatus.PASS,
                system_id="FTX01",
            ),
        ),
        review=(
            OvkReviewDecision(
                observation_id="o1",
                source_text="B1 FTX01 34 l/s 40 l/s",
                evidence_ref="doc#page=1",
                reason="unlabelled_airflow_value",
                status=review_status,
                reviewer="tester" if review_status is not ReviewStatus.PENDING else None,
            ),
        ),
        coverage=InspectionCoverage(
            inspection_id="ovk-001",
            aggregat=(
                AggregatCoverage(
                    aggregat_id="agg-1", label="FTX01", status=AggregatStatus.BESIKTIGAD
                ),
            ),
            system_list_confirmation=SystemForteckningBekraftelse(
                confirmed_by="Test Besiktningsman", role=BekraftelseRoll.BESIKTNINGSMAN
            ),
        ),
    )


def test_repository_roundtrip_and_protocol_ready(tmp_path: Path) -> None:
    repository = OvkWorkflowRepository(tmp_path)
    record = _record()
    repository.save(record)
    loaded = repository.load("p1", "ovk-001")

    assert loaded.inspection.conclusion.value == "approved"
    assert loaded.protocol_ready is True
    assert loaded.review[0].status is ReviewStatus.ACCEPTED
    html = protocol_html(loaded)
    assert "OVK-protokoll" in html
    assert "Testobjekt" in html


def test_empty_checkpoint_set_is_pending() -> None:
    record = build_record(
        inspection_id="ovk-001",
        ovk_object=OvkObject(
            object_id="object-1",
            project_id="p1",
            building_id="building-1",
            name="Testobjekt",
        ),
        coverage=InspectionCoverage(
            inspection_id="ovk-001",
            aggregat=(
                AggregatCoverage(
                    aggregat_id="agg-1", label="FTX01", status=AggregatStatus.BESIKTIGAD
                ),
            ),
            system_list_confirmation=SystemForteckningBekraftelse(
                confirmed_by="Test Besiktningsman", role=BekraftelseRoll.BESIKTNINGSMAN
            ),
        ),
    )
    assert record.inspection.conclusion.value == "pending"
    assert record.protocol_ready is False


def test_pending_review_blocks_protocol() -> None:
    record = _record(review_status=ReviewStatus.PENDING)
    assert record.unresolved_review_count == 1
    assert record.protocol_ready is False


def _write_entitlements(root: Path) -> None:
    target = root / "config" / "customers" / "acme"
    target.mkdir(parents=True, exist_ok=True)
    (target / "entitlements.json").write_text(
        json.dumps(
            {
                "customer_id": "acme",
                "modules": [{"id": "ovk", "active": True}],
            }
        ),
        encoding="utf-8",
    )


def _client(tmp_path: Path, monkeypatch: MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    _write_entitlements(tmp_path)
    return TestClient(create_app(tmp_path))


def _based_on(client: TestClient, url: str) -> dict[str, str]:
    """Sparningen utgår från postens nuvarande revision, som en klient som nyss läst den."""
    return {"X-OVK-Base-Revision": client.get(url).headers["X-OVK-Record-Revision"]}


def _workflow_payload(
    *,
    status: str = "pass",
    review_status: str = "accepted",
) -> dict[str, object]:
    return {
        "inspection": {
            "object": {
                "object_id": "object-1",
                "project_id": "ignored-by-route",
                "building_id": "building-1",
                "name": "Testobjekt",
                "address": "Testvägen 1",
            },
            "systems": [
                {
                    "system_id": "FTX01",
                    "system_type": "FTX",
                    "label": "System FTX01",
                    "source_ref": "doc#page=1",
                }
            ],
            "checkpoints": [
                {
                    "checkpoint_id": "cp1",
                    "label": "Drift och funktion",
                    "status": status,
                    "system_id": "FTX01",
                    "note": "Kontrollerad",
                    "origin": "observed",
                    "evidence_ref": None,
                }
            ],
            "measurements": [],
            "findings": [],
            "actions": [],
        },
        "coverage": {
            "inspection_id": "ovk-001",
            "aggregat": [
                {
                    "aggregat_id": "agg-1",
                    "label": "FTX01",
                    "status": "besiktigad",
                    "justification": "",
                    "stated_by": "",
                }
            ],
            "system_list_confirmation": {
                "confirmed_by": "Test Besiktningsman",
                "role": "besiktningsman",
            },
        },
        "review": [
            {
                "observation_id": "o1",
                "source_text": "B1 FTX01 34 l/s 40 l/s",
                "evidence_ref": "doc#page=1",
                "reason": "unlabelled_airflow_value",
                "status": review_status,
                "reviewer": "tester" if review_status != "pending" else None,
                "note": "granskad",
            }
        ],
    }


def test_workbench_saves_loads_and_exports_protocol(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    url = "/api/ovk/projects/p1/inspections/ovk-001"
    saved = client.put(url, json=_workflow_payload())
    assert saved.status_code == 200
    assert saved.json()["protocol_ready"] is True
    assert saved.json()["inspection"]["object"]["project_id"] == "p1"

    loaded = client.get(url)
    assert loaded.status_code == 200
    assert loaded.json()["inspection"]["conclusion"] == "approved"

    protocol = client.get(url + "/protocol")
    assert protocol.status_code == 200
    assert "OVK-protokoll" in protocol.text


def test_workbench_blocks_protocol_with_pending_review(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    url = "/api/ovk/projects/p1/inspections/ovk-002"
    saved = client.put(url, json=_workflow_payload(review_status="pending"))
    assert saved.status_code == 200
    assert saved.json()["protocol_ready"] is False

    protocol = client.get(url + "/protocol")
    assert protocol.status_code == 409
    assert protocol.json()["detail"]["code"] == "OVK_PROTOCOL_NOT_READY"


def test_workflow_page_preserves_project_and_saved_inspection_context(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    page = client.get("/ovk/besiktning?project_id=p1&inspection_id=ovk-001")
    script = client.get("/ovk/besiktning/app.js")

    assert page.status_code == 200
    assert "Besiktningsunderlag" in page.text
    assert "/ovk/besiktning/app.js" in page.text
    assert script.status_code == 200
    assert "get('project_id')" in script.text
    assert "get('inspection_id')" in script.text
    assert "await loadInspection(projectId, requestedInspection)" in script.text
    assert "$('building').value = object.building_id" in script.text
    assert "$('checkpoints').value = lines(inspection.checkpoints" in script.text
    assert "measurements: previousInspection.measurements || []" in script.text
    assert "findings: previousInspection.findings || []" in script.text
    assert "actions: previousInspection.actions || []" in script.text
    assert "'/ovk/falt' + (query ? '?' + query : '')" in script.text


def test_guided_draft_remains_pending_and_preserves_property_context(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    page = client.get("/ovk/besiktning?new=1&project_id=p1")
    script = client.get("/ovk/besiktning/app.js")
    assert page.status_code == 200
    assert 'id="draftProperty"' in page.text
    assert 'id="draftBuilding"' in page.text
    assert 'id="draftSystems"' in page.text
    assert "checkpoints:[],measurements:[],findings:[],actions:[]" in script.text

    url = "/api/ovk/projects/p1/inspections/ovk-guided"
    saved = client.put(
        url,
        json={
            "inspection": {
                "object": {
                    "object_id": "fastighet-1",
                    "project_id": "p1",
                    "building_id": "hus-a",
                    "name": "Björken 12 · Hus A",
                    "address": "Testvägen 1",
                },
                "systems": [
                    {"system_id": "LB01", "system_type": "FTX", "label": "Huvudsystem"},
                    {"system_id": "FF01", "system_type": "F", "label": "Frånluft"},
                ],
                "checkpoints": [],
                "measurements": [],
                "findings": [],
                "actions": [],
            },
            "review": [],
        },
    )
    assert saved.status_code == 200
    loaded = client.get(url).json()
    assert loaded["inspection"]["object"]["object_id"] == "fastighet-1"
    assert loaded["inspection"]["object"]["building_id"] == "hus-a"
    assert len(loaded["inspection"]["systems"]) == 2
    assert loaded["inspection"]["conclusion"] == "pending"
    assert loaded["protocol_ready"] is False
    assert client.get(url + "/protocol").status_code == 409


def test_planning_validates_registry_and_survives_legacy_save(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    assert (
        client.put(
            "/api/ovk/projects/p1/fastighet/object-1",
            json={
                "fastighetsbeteckning": "Björken 12",
                "byggnader": [{"byggnad_id": "building-1", "internt_namn": "Hus A"}],
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/ovk/registry/besiktningsman/person-1",
            json={
                "namn": "Test Kontrollant",
                "behorighet": "K",
                "certifieringsorgan": "Test",
                "certnummer": "123",
                "giltig_till": "2030-12-31",
            },
        ).status_code
        == 200
    )
    url = "/api/ovk/projects/p1/inspections/ovk-001"
    payload = _workflow_payload()
    planning = {
        "inspector_id": "person-1",
        "planned_date": "2027-01-15",
        "inspection_type": "aterkommande",
    }
    payload["planning"] = planning
    structure_url = "/api/ovk/projects/p1/fastighet/object-1/byggnad/building-1/struktur"
    structure = {
        "units": [
            {
                "unit_id": "u1",
                "number": "1203",
                "kind": "apartment",
                "rooms": [{"room_id": "r1", "name": "Kök"}],
            }
        ],
        "systems": [{"system_id": "FTX01", "system_type": "FTX", "label": "LB01"}],
        "technical_spaces": [],
    }
    assert client.put(structure_url, json=structure).status_code == 200
    wrong_structure = {
        **structure,
        "systems": [{"system_id": "other", "system_type": "F", "label": "FF01"}],
    }
    assert client.put(structure_url, json=wrong_structure).status_code == 200
    assert client.put(url, json=payload).status_code == 422
    assert client.put(structure_url, json=structure).status_code == 200
    assert client.put(url, json=payload).status_code == 200
    captured = client.get(url).json()
    assert captured["building_structure"] == structure
    assert len(captured["building_structure_sha256"]) == 64
    assert client.put(structure_url, json={**structure, "units": []}).status_code == 200
    assert client.put(url, json={**payload, "building_structure": {}}).status_code == 200
    assert client.get(url).json()["building_structure"] == structure
    assert (
        client.get(url).json()["building_structure_sha256"] == captured["building_structure_sha256"]
    )
    assert client.get(url).json()["planning"] == planning
    assert client.put(url, json=_workflow_payload()).status_code == 200
    assert client.get(url).json()["planning"] == planning
    payload["planning"] = {**planning, "planned_date": "2031-01-01"}
    assert client.put(url, json=payload, headers=_based_on(client, url)).status_code == 422
    assert client.get(url).json()["planning"] == planning
    payload["planning"] = {**planning, "inspector_id": "missing"}
    assert client.put(url, json=payload, headers=_based_on(client, url)).status_code == 422
    assert client.get(url).json()["planning"] == planning


def test_recurring_reference_is_scoped_and_preserved(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    root = "/api/ovk/projects/p1"
    assert (
        client.put(
            root + "/fastighet/object-1",
            json={
                "fastighetsbeteckning": "Björken 12",
                "byggnader": [{"byggnad_id": "building-1", "internt_namn": "Hus A"}],
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/ovk/registry/besiktningsman/person-1",
            json={
                "namn": "Test",
                "behorighet": "K",
                "certifieringsorgan": "Test",
                "certnummer": "123",
                "giltig_till": "2030-12-31",
            },
        ).status_code
        == 200
    )
    old = _workflow_payload()
    assert client.put(root + "/inspections/ovk-001", json=old).status_code == 200
    payload = _workflow_payload()
    planning = {
        "inspector_id": "person-1",
        "planned_date": "2027-01-15",
        "inspection_type": "aterkommande",
        "previous_inspection_id": "ovk-001",
    }
    payload["planning"] = planning
    payload.pop("coverage")
    url = root + "/inspections/ovk-002"
    assert client.put(url, json=payload).status_code == 200
    assert client.get(url).json()["planning"] == planning
    payload["planning"] = {**planning, "previous_inspection_id": "missing"}
    assert client.put(url, json=payload, headers=_based_on(client, url)).status_code == 422
    payload["planning"] = {**planning, "previous_inspection_id": "ovk-003"}
    assert client.put(root + "/inspections/ovk-003", json=payload).status_code == 422
    assert client.get(url).json()["planning"] == planning


def test_property_first_api_chain_from_empty_project_list(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/projects").json() == []
    page = client.get("/ovk/besiktning?new=1")
    script = client.get("/ovk/besiktning/app.js")
    assert page.status_code == script.status_code == 200
    assert 'id="propertySearchForm"' in page.text
    assert 'id="newPropertyForm" hidden' in page.text
    assert 'id="draftForm" hidden' in page.text
    assert "normalizeDesignation" in script.text
    assert "OVK" in page.text

    project_id = "project-new"
    project_payload = {"name": "Eken 12:3", "project_id": project_id}
    project = client.post("/api/projects", json=project_payload)
    assert project.status_code == 201
    assert project.json()["project_name"] == "Eken 12:3"
    assert client.post("/api/projects", json=project_payload).status_code == 409
    assert len(client.get("/api/projects").json()) == 1

    root = f"/api/ovk/projects/{project_id}"
    property_url = root + "/fastighet/property-new"
    missing = client.get(property_url)
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "FASTIGHET_NOT_FOUND"
    saved = client.put(
        property_url,
        json={
            "fastighetsbeteckning": "Eken 12:3",
            "byggnadens_adress": {"gata": "Testvägen 1", "ort": "Östersund"},
            "fastighetstyp": "flerbostadshus",
            "byggnader": [{"byggnad_id": "building-new", "internt_namn": "Hus A"}],
        },
    )
    assert saved.status_code == 200
    property_record = client.get(property_url).json()
    assert client.get(root + "/fastighet").json()["fastigheter"] == [property_record]

    assert (
        client.put(
            "/api/ovk/registry/besiktningsman/person-1",
            json={
                "namn": "Test Kontrollant",
                "behorighet": "K",
                "certifieringsorgan": "Test",
                "certnummer": "123",
            },
        ).status_code
        == 200
    )
    structure_url = property_url + "/byggnad/building-new/struktur"
    assert client.get(structure_url).json() == {
        "units": [],
        "systems": [],
        "technical_spaces": [],
    }
    payload = {
        "inspection": {
            "object": {
                "object_id": "property-new",
                "project_id": project_id,
                "building_id": "building-new",
                "name": "Eken 12:3 · Hus A",
                "address": "Testvägen 1, Östersund",
            },
            "systems": [{"system_id": "LB01", "system_type": "FTX", "label": "LB01"}],
            "checkpoints": [],
            "measurements": [],
            "findings": [],
            "actions": [],
        },
        "review": [],
        "planning": {
            "inspector_id": "person-1",
            "planned_date": "2027-01-15",
            "inspection_type": "aterkommande",
            "previous_inspection_id": None,
        },
    }
    first_url = root + "/inspections/ovk-first"
    assert client.put(first_url, json=payload).status_code == 200
    first = client.get(first_url).json()
    assert first["inspection"]["conclusion"] == "pending"
    assert first["protocol_ready"] is False

    # Ett återbesök använder samma projekt och fastighet, men ett nytt OVK-ID.
    second_url = root + "/inspections/ovk-second"
    assert client.put(second_url, json=payload).status_code == 200
    assert client.get(first_url).json() == first
    assert client.get(second_url).json()["inspection"]["object"] == first["inspection"]["object"]
    assert len(client.get(root + "/inspections").json()["inspections"]) == 2
    assert len(client.get("/api/projects").json()) == 1
    assert client.get(property_url).json() == property_record


def test_property_first_field_inventory_promotion_and_recurring_inspection(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Exercise the real HTTP surfaces across two inspections of a new property."""
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/projects").json() == []
    project = "property-lifecycle"
    root = f"/api/ovk/projects/{project}"
    property_url = root + "/fastighet/eken"
    structure_url = property_url + "/byggnad/hus-a/struktur"
    assert (
        client.post("/api/projects", json={"name": "Eken 12:3", "project_id": project}).status_code
        == 201
    )
    assert (
        client.put(
            property_url,
            json={
                "fastighetsbeteckning": "Eken 12:3",
                "fastighetstyp": "flerbostadshus",
                "byggnader": [{"byggnad_id": "hus-a", "internt_namn": "Hus A"}],
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/ovk/registry/besiktningsman/inspector-1",
            json={
                "namn": "Test Kontrollant",
                "behorighet": "K",
                "certifieringsorgan": "Test",
                "certnummer": "123",
                "giltig_till": "2035-12-31",
            },
        ).status_code
        == 200
    )
    empty_structure: dict[str, list[Any]] = {"units": [], "systems": [], "technical_spaces": []}
    assert client.get(structure_url).json() == empty_structure
    first_workflow = root + "/inspections/ovk-first"
    first_field = root + "/field/ovk-first"
    second_workflow = root + "/inspections/ovk-second"
    second_field = root + "/field/ovk-second"
    system = {"system_id": "LB01", "system_type": "FTX", "label": "LB01"}
    draft: dict[str, Any] = {
        "inspection": {
            "object": {
                "object_id": "eken",
                "project_id": project,
                "building_id": "hus-a",
                "name": "Eken 12:3 · Hus A",
            },
            "systems": [system],
            "checkpoints": [],
            "measurements": [],
            "findings": [],
            "actions": [],
        },
        "review": [],
        "planning": {
            "inspector_id": "inspector-1",
            "planned_date": "2027-01-15",
            "inspection_type": "aterkommande",
        },
    }
    created = client.put(first_workflow, json=draft)
    assert created.status_code == 200, created.text
    assert created.json()["building_structure"] == empty_structure
    assert created.json()["protocol_ready"] is False
    assert client.put(first_field + "/context", json={"system_type": "FTX"}).status_code == 200

    # Simulate the structural result of field inventory and template copying,
    # without pretending that an HTTP test executes the mobile UI.
    photo_bytes = b"test-photo-evidence"
    field: dict[str, Any] = {
        "inspection_id": "ovk-first",
        "units": [
            {
                "unit_id": "u1",
                "number": "1101",
                "kind": "apartment",
                "status": "anmarkning",
                "checked_at": "2027-01-15T10:05:00+01:00",
            },
            {
                "unit_id": "u2",
                "number": "1201",
                "kind": "apartment",
                "status": "ua",
                "checked_at": "2027-01-15T10:15:00+01:00",
            },
        ],
        "rooms": [
            {"room_id": "r1", "unit_id": "u1", "name": "Badrum"},
            {"room_id": "r2", "unit_id": "u2", "name": "Badrum"},
        ],
        "measurements": [
            {
                "measurement_id": "m1",
                "unit_id": "u1",
                "room_id": "r1",
                "point_type": "franluftsdon",
                "point_label": "FL01",
                "system_id": "LB01",
                "designed_value": "15",
                "measured_value": "12",
                "measurable": True,
                "unit_of_measure": "l/s",
            },
            {
                "measurement_id": "m2",
                "unit_id": "u2",
                "room_id": "r2",
                "point_type": "franluftsdon",
                "point_label": "FL01",
                "designed_value": "15",
                "measured_value": "15",
                "measurable": True,
                "unit_of_measure": "l/s",
            },
        ],
        "findings": [
            {
                "finding_id": "f1",
                "unit_id": "u1",
                "room_id": "r1",
                "defect_type": "contaminated_extract_terminal",
                "description": "Smutsigt don",
                "severity": "minor",
                "system_id": "LB01",
                "classification": 1,
            }
        ],
        "photos": [
            {
                "photo_id": "photo-1",
                "unit_id": "u1",
                "unit_number": "1101",
                "room_id": "r1",
                "finding_id": "f1",
                "defect_type": "contaminated_extract_terminal",
                "captured_at": "2027-01-15T10:00:00+01:00",
                "captured_by": "Test Kontrollant",
                "local_uri": "indexeddb:photo-1",
                "sha256": sha256(photo_bytes).hexdigest(),
                "mime_type": "image/jpeg",
                "sync_status": "local",
            }
        ],
    }
    synced = client.put(first_field + "/sync", json=field)
    assert synced.status_code == 200, synced.text
    uploaded = client.put(
        first_field + "/media/photo-1",
        content=photo_bytes,
        headers={
            "Content-Type": "image/jpeg",
            "X-OVK-Base-Revision": synced.json()["snapshot_sha256"],
        },
    )
    assert uploaded.status_code == 200, uploaded.text
    original_snapshot = client.get(first_field + "/sync").json()
    original_record = client.get(first_workflow).json()

    # The current office workflow requires registering the real system first.
    register = client.put(structure_url, json={**empty_structure, "systems": [system]})
    assert register.status_code == 200, register.text
    promotion = structure_url + "/aterforing/ovk-first"
    preview = client.post(promotion + "/preview", json={})
    assert preview.status_code == 200, preview.text
    assert preview.json()["unresolved"] == [{"point_id": "m2", "label": "1201 / Badrum / FL01"}]
    assignments = {"m2": "LB01"}
    reviewed = client.post(promotion + "/preview", json={"assignments": assignments})
    assert reviewed.status_code == 200, reviewed.text
    assert len(reviewed.json()["additions"]) == 6
    applied = client.post(
        promotion + "/apply",
        json={
            "assignments": assignments,
            "preview_token": reviewed.json()["preview_token"],
            "confirmed": True,
        },
    )
    assert applied.status_code == 200, applied.text
    inventory = client.get(structure_url).json()
    assert inventory == applied.json()["structure"]
    assert [unit["unit_id"] for unit in inventory["units"]] == ["u1", "u2"]
    for index, unit in enumerate(inventory["units"], start=1):
        room = unit["rooms"][0]
        point = room["measurement_points"][0]
        assert room["room_id"] == f"r{index}"
        assert point == {
            "point_id": f"m{index}",
            "label": "FL01",
            "point_type": "franluftsdon",
            "system_id": "LB01",
            "designed_value": "15",
            "unit_of_measure": "l/s",
        }
    assert client.get(first_workflow).json() == original_record
    assert client.get(first_field + "/sync").json() == original_snapshot

    # An unfinished workflow must not become a historical predecessor.
    recurring = deepcopy(draft)
    recurring["planning"]["planned_date"] = "2030-01-15"
    recurring["planning"]["previous_inspection_id"] = "ovk-first"
    assert client.put(second_workflow, json=recurring).status_code == 422

    # Explicit workflow review, not a conclusion inferred from field results.
    completed = deepcopy(draft)
    completed["inspection"]["checkpoints"] = [
        {
            "checkpoint_id": "cp1",
            "label": "Drift och funktion",
            "status": "pass",
            "system_id": "LB01",
        }
    ]
    completed["coverage"] = {
        "inspection_id": "ovk-first",
        "aggregat": [{"aggregat_id": "agg-1", "label": "LB01", "status": "besiktigad"}],
        "system_list_confirmation": {
            "confirmed_by": "Test Kontrollant",
            "role": "besiktningsman",
        },
    }
    finalized = client.put(
        first_workflow, json=completed, headers=_based_on(client, first_workflow)
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["protocol_ready"] is True
    assert finalized.json()["building_structure"] == empty_structure
    original_record = client.get(first_workflow).json()

    created = client.put(second_workflow, json=recurring)
    assert created.status_code == 200, created.text
    next_record = created.json()
    assert next_record["building_structure"] == inventory
    assert next_record["inspection"]["inspection_id"] == "ovk-second"
    assert next_record["inspection"]["object"] == original_record["inspection"]["object"]
    assert next_record["inspection"]["measurements"] == []
    assert next_record["inspection"]["findings"] == []
    assert next_record["inspection"]["conclusion"] == "pending"
    assert next_record["protocol_ready"] is False
    assert client.get(second_field + "/sync").status_code == 404

    history = client.get(second_field + "/history")
    assert history.status_code == 200, history.text
    previous = history.json()
    assert previous["source_inspection_id"] == "ovk-first"
    assert previous["snapshot_sha256"] == original_snapshot["snapshot_sha256"]
    historical_points = previous["historical_measurements"]
    assert [point["measurement_id"] for point in historical_points] == ["m1", "m2"]
    assert historical_points[0]["measured_value"] == "12"
    assert historical_points[0]["system_id"] == "LB01"
    # The original point lacking a system is not silently rewritten by promotion.
    assert historical_points[1].get("system_id") is None
    finding = previous["historical_findings"][0]
    assert finding["finding_id"] == "f1"
    assert finding["unit_id"] == "u1"
    photo = finding["photos"][0]
    assert photo["historical"] is True
    assert photo["verified"] is True
    assert client.get(photo["content_url"]).content == photo_bytes

    # Starting the second round uses the same structural IDs but fresh results.
    assert client.put(second_field + "/context", json={"system_type": "FTX"}).status_code == 200
    current_field = {
        "inspection_id": "ovk-second",
        "units": [
            {
                "unit_id": unit["unit_id"],
                "number": unit["number"],
                "kind": unit["kind"],
                "status": "ej_paborjad",
            }
            for unit in next_record["building_structure"]["units"]
        ],
        "rooms": [
            {"room_id": room["room_id"], "unit_id": unit["unit_id"], "name": room["name"]}
            for unit in next_record["building_structure"]["units"]
            for room in unit["rooms"]
        ],
        "measurements": [
            {
                "measurement_id": point["point_id"],
                "unit_id": unit["unit_id"],
                "room_id": room["room_id"],
                "point_type": point["point_type"],
                "point_label": point["label"],
                "system_id": point["system_id"],
                "designed_value": point["designed_value"],
                "unit_of_measure": point["unit_of_measure"],
                "measurable": True,
                "measured_value": None,
            }
            for unit in next_record["building_structure"]["units"]
            for room in unit["rooms"]
            for point in room.get("measurement_points", [])
        ],
        "findings": [],
        "photos": [],
    }
    second_sync = client.put(second_field + "/sync", json=current_field)
    assert second_sync.status_code == 200, second_sync.text
    current = client.get(second_field + "/sync").json()["payload"]
    assert [point["measurement_id"] for point in current["measurements"]] == ["m1", "m2"]
    assert all(point["measured_value"] is None for point in current["measurements"])
    assert all(unit["checked_at"] is None for unit in current["units"])
    assert all(unit["status"] == "ej_paborjad" for unit in current["units"])
    assert current["findings"] == current["photos"] == []
    assert client.get(first_workflow).json() == original_record
    assert client.get(first_field + "/sync").json() == original_snapshot
    assert len(client.get("/api/projects").json()) == 1
    assert len(client.get(root + "/inspections").json()["inspections"]) == 2


def test_new_property_does_not_inherit_the_dashboard_project() -> None:
    """Utan aktivt projektval ska fastigheten få ett eget projekt med sitt namn."""
    from importlib import resources

    script = (resources.files("crow_ovk_module") / "assets" / "workflow.js").read_text("utf-8")
    assert "$('newPropertyProject').value=requestedProject" not in script
    assert "projectId:existingProject?.project_id||randomId('project-')" in script
