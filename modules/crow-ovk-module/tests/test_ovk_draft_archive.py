"""Ett protokollutkast som har ändrats ersätts inte utan fråga, och sparas undan först."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_ovk_workflow import _client

from crow_ovk import OvkObject, VentilationSystemRef
from crow_ovk_module.ovk_draft_archive import (
    archive,
    has_unsaved_work,
    list_archived,
    load_archived,
)
from crow_ovk_workflow import OvkWorkflowRepository, ReviewStatus, build_record
from crow_ovk_workflow.models import InspectionPlanning, OvkReviewDecision

BASE = "/api/ovk/projects/p1/field/ovk-utkast"
SAVED = BASE + "/protokoll-utkast/sparade"


def _prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, dict[str, str]]:
    client: TestClient = _client(tmp_path, monkeypatch)
    OvkWorkflowRepository(tmp_path).save(
        build_record(
            inspection_id="ovk-utkast",
            ovk_object=OvkObject("object-1", "p1", "building-1", "Building"),
            systems=(VentilationSystemRef("FTX01", "FTX", "System FTX01"),),
            planning=InspectionPlanning("person-1", date.today(), "aterkommande"),
        )
    )
    assert client.put(f"{BASE}/context", json={"system_type": "FTX"}).status_code == 200
    synced = client.put(
        f"{BASE}/sync",
        json={
            "inspection_id": "ovk-utkast",
            "system_type": "FTX",
            "units": [
                {
                    "unit_id": "u1",
                    "number": "1201",
                    "kind": "apartment",
                    "status": "anmarkning",
                    "checked_at": "2026-08-20T10:00:00+02:00",
                }
            ],
            "rooms": [{"room_id": "r1", "unit_id": "u1", "name": "Badrum"}],
            "findings": [
                {
                    "finding_id": "f1",
                    "unit_id": "u1",
                    "room_id": "r1",
                    "defect_type": "contaminated_extract_terminal",
                    "description": "Skitig ventil i bad",
                    "severity": "minor",
                    "classification": 1,
                }
            ],
        },
    )
    assert synced.status_code == 200, synced.text
    return client, {"X-OVK-Base-Revision": synced.json()["snapshot_sha256"]}


def _decide(tmp_path: Path, note: str = "Kontrollerad på plats") -> None:
    """Arbete på utkastet: ett granskningsbeslut läggs på posten."""
    workflows = OvkWorkflowRepository(tmp_path)
    record = workflows.load("p1", "ovk-utkast")
    decision = OvkReviewDecision(
        observation_id="o1",
        source_text="Skitig ventil i bad",
        evidence_ref="f1",
        reason="needs_review",
        status=ReviewStatus.ACCEPTED,
        reviewer="Stoffe",
        note=note,
    )
    workflows.save(replace(record, review=(decision,)))


def test_first_build_and_untouched_rebuild_need_no_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, headers = _prepared(tmp_path, monkeypatch)
    workflows = OvkWorkflowRepository(tmp_path)
    # En nyplanerad post har inget att förlora.
    assert not has_unsaved_work(tmp_path, workflows.load("p1", "ovk-utkast"))

    first = client.post(f"{BASE}/protokoll-utkast", headers=headers, json={})
    again = client.post(f"{BASE}/protokoll-utkast", headers=headers, json={})

    assert first.status_code == 200, first.text
    assert again.status_code == 200, again.text
    assert first.json()["sparat_utkast"] is None
    assert again.json()["sparat_utkast"] is None
    assert client.get(SAVED).json()["sparade"] == []
    assert not has_unsaved_work(tmp_path, workflows.load("p1", "ovk-utkast"))


def test_changed_draft_is_not_replaced_without_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, headers = _prepared(tmp_path, monkeypatch)
    assert client.post(f"{BASE}/protokoll-utkast", headers=headers, json={}).status_code == 200
    _decide(tmp_path)
    workflows = OvkWorkflowRepository(tmp_path)
    before = workflows.load("p1", "ovk-utkast")

    for body in ({}, {"confirm_replace": False}):
        refused = client.post(f"{BASE}/protokoll-utkast", headers=headers, json=body)

        assert refused.status_code == 409
        detail = refused.json()["detail"]
        assert detail["code"] == "OVK_DRAFT_REPLACE_CONFIRMATION_REQUIRED"
        assert detail["summary"]["granskningsbeslut"] == 1
        assert detail["summary"]["anmarkningar"] == 1
    # Ingenting är ändrat och ingenting sparat undan.
    assert workflows.load("p1", "ovk-utkast") == before
    assert client.get(SAVED).json()["sparade"] == []
    for bad in ("ja", 1, None):
        invalid = client.post(
            f"{BASE}/protokoll-utkast", headers=headers, json={"confirm_replace": bad}
        )
        assert invalid.status_code == 422
    assert workflows.load("p1", "ovk-utkast") == before


def test_confirmed_replace_saves_the_work_first_and_it_can_be_restored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, headers = _prepared(tmp_path, monkeypatch)
    assert client.post(f"{BASE}/protokoll-utkast", headers=headers, json={}).status_code == 200
    _decide(tmp_path)
    workflows = OvkWorkflowRepository(tmp_path)
    worked = workflows.load("p1", "ovk-utkast")

    replaced = client.post(
        f"{BASE}/protokoll-utkast", headers=headers, json={"confirm_replace": True}
    )

    assert replaced.status_code == 200, replaced.text
    archive_id = replaced.json()["sparat_utkast"]
    assert workflows.load("p1", "ovk-utkast").review == ()
    saved = client.get(SAVED).json()
    assert (saved["project_id"], saved["inspection_id"]) == ("p1", "ovk-utkast")
    assert [item["archive_id"] for item in saved["sparade"]] == [archive_id]
    assert saved["sparade"][0]["summary"]["granskningsbeslut"] == 1
    assert saved["sparade"][0]["reason"] == "ersatt av nytt utkast"
    # Kopian är hela posten som den var.
    assert load_archived(tmp_path, "p1", "ovk-utkast", archive_id) == worked
    # Den ligger inte bland besiktningarna, där varje fil läses som en besiktning.
    assert [r.inspection.inspection_id for r in workflows.list("p1")] == ["ovk-utkast"]

    restored = client.post(f"{SAVED}/{archive_id}/aterstall")

    assert restored.status_code == 200, restored.text
    # Det nybyggda utkastet var orört och behövde inte sparas undan.
    assert restored.json() == {
        "aterstallt": archive_id,
        "sparat_utkast": None,
        "record": restored.json()["record"],
    }
    back = workflows.load("p1", "ovk-utkast")
    assert back.review == worked.review
    assert back.inspection == worked.inspection
    # Det återställda är arbete: nästa bygge frågar igen.
    assert client.post(f"{BASE}/protokoll-utkast", headers=headers, json={}).status_code == 409


def test_restore_saves_what_it_replaces_and_keeps_current_planning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, headers = _prepared(tmp_path, monkeypatch)
    assert client.post(f"{BASE}/protokoll-utkast", headers=headers, json={}).status_code == 200
    _decide(tmp_path, "första")
    first = client.post(
        f"{BASE}/protokoll-utkast", headers=headers, json={"confirm_replace": True}
    ).json()["sparat_utkast"]
    _decide(tmp_path, "andra")
    workflows = OvkWorkflowRepository(tmp_path)
    current = workflows.load("p1", "ovk-utkast")
    assert current.planning is not None
    replanned = replace(current.planning, inspector_id="person-2")
    workflows.save(replace(current, planning=replanned))

    restored = client.post(f"{SAVED}/{first}/aterstall")

    assert restored.status_code == 200, restored.text
    second = restored.json()["sparat_utkast"]
    assert second is not None and second != first
    assert load_archived(tmp_path, "p1", "ovk-utkast", second).review[0].note == "andra"
    back = workflows.load("p1", "ovk-utkast")
    assert back.review[0].note == "första"
    # Planeringen är besiktningens nuvarande, inte den sparade kopians.
    assert back.planning == replanned
    assert len(client.get(SAVED).json()["sparade"]) == 2


def test_saved_drafts_are_scoped_validated_and_reported_when_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, headers = _prepared(tmp_path, monkeypatch)
    assert client.post(f"{BASE}/protokoll-utkast", headers=headers, json={}).status_code == 200
    _decide(tmp_path)
    record = OvkWorkflowRepository(tmp_path).load("p1", "ovk-utkast")
    archive_id = archive(tmp_path, record, "test")
    # Samma innehåll sparas en gång.
    assert archive(tmp_path, record, "test") == archive_id

    for missing in ("20260101T000000Z-000000000000", "..%2F..%2Fovk%2Fovk-utkast", "x"):
        assert client.post(f"{SAVED}/{missing}/aterstall").status_code == 404
    other = "/api/ovk/projects/p2/field/ovk-utkast/protokoll-utkast/sparade"
    assert client.get(other).json()["sparade"] == []
    assert client.post(f"{other}/{archive_id}/aterstall").status_code == 404

    # En ändrad kopia återställs inte, och listan säger att den inte går att läsa.
    path = tmp_path / "projects" / "p1" / "ovk-utkast-sparade" / "ovk-utkast" / f"{archive_id}.json"
    path.write_text(path.read_text(encoding="utf-8").replace("Stoffe", "Någon annan"), "utf-8")
    assert client.post(f"{SAVED}/{archive_id}/aterstall").status_code == 409
    with pytest.raises(ValueError, match="does not belong"):
        load_archived(tmp_path, "p1", "ovk-utkast", archive_id)
    path.write_text("{", encoding="utf-8")
    assert list_archived(tmp_path, "p1", "ovk-utkast") == [
        {"archive_id": archive_id, "olasbar": True}
    ]
    assert client.post(f"{SAVED}/{archive_id}/aterstall").status_code == 409
