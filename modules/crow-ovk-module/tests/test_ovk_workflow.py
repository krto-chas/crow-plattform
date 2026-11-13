from __future__ import annotations

import json
from pathlib import Path

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
        "systems": [],
        "technical_spaces": [],
    }
    structure["systems"] = [{"system_id": "FTX01", "system_type": "FTX", "label": "LB01"}]
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
    assert client.put(url, json=payload).status_code == 422
    assert client.get(url).json()["planning"] == planning
    payload["planning"] = {**planning, "inspector_id": "missing"}
    assert client.put(url, json=payload).status_code == 422
    assert client.get(url).json()["planning"] == planning
