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


def _decision(note: str) -> OvkReviewDecision:
    return OvkReviewDecision(
        observation_id="o1",
        source_text="Skitig ventil i bad",
        evidence_ref="f1",
        reason="needs_review",
        status=ReviewStatus.ACCEPTED,
        reviewer="Stoffe",
        note=note,
    )


def _decide(tmp_path: Path, note: str = "Kontrollerad på plats") -> None:
    """Arbete på utkastet: ett granskningsbeslut läggs på posten."""
    workflows = OvkWorkflowRepository(tmp_path)
    record = workflows.load("p1", "ovk-utkast")
    workflows.save(replace(record, review=(_decision(note),)))


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
        "protokollkalla_aktuell": True,
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
    workflows = OvkWorkflowRepository(tmp_path)
    record = workflows.load("p1", "ovk-utkast")
    archive_id = archive(tmp_path, record, "test")

    for missing in ("20260101T000000Z-000000000000", "20260101T000000Z-00000000000g", "a.b"):
        assert client.post(f"{SAVED}/{missing}/aterstall").status_code == 404
    # Ett annat projekt med en besiktning med samma id når inte kopian.
    workflows.save(
        build_record(
            inspection_id="ovk-utkast",
            ovk_object=OvkObject("object-1", "p2", "building-1", "Building"),
            systems=(VentilationSystemRef("FTX01", "FTX", "System FTX01"),),
            planning=InspectionPlanning("person-1", date.today(), "aterkommande"),
        )
    )
    other = "/api/ovk/projects/p2/field/ovk-utkast/protokoll-utkast/sparade"
    assert client.get(other).json()["sparade"] == []
    refused = client.post(f"{other}/{archive_id}/aterstall")
    assert (refused.status_code, refused.json()["detail"]["code"]) == (
        404,
        "OVK_SAVED_DRAFT_NOT_FOUND",
    )
    # Ett projekt som inte finns ger 404 redan i omfångskontrollen (ADR-013 punkt 3).
    unknown = "/api/ovk/projects/saknas/field/ovk-utkast/protokoll-utkast/sparade"
    for response in (client.get(unknown), client.post(f"{unknown}/{archive_id}/aterstall")):
        assert (response.status_code, response.json()["detail"]["code"]) == (
            404,
            "OVK_PROJECT_NOT_FOUND",
        )

    # En ändrad kopia återställs inte, och listan säger att den inte går att läsa.
    path = tmp_path / "projects" / "p1" / "ovk-utkast-sparade" / "ovk-utkast" / f"{archive_id}.json"
    path.write_text(path.read_text(encoding="utf-8").replace("Stoffe", "Någon annan"), "utf-8")
    changed = client.post(f"{SAVED}/{archive_id}/aterstall")
    assert (changed.status_code, changed.json()["detail"]["code"]) == (
        409,
        "OVK_SAVED_DRAFT_UNREADABLE",
    )
    with pytest.raises(ValueError, match="does not belong"):
        load_archived(tmp_path, "p1", "ovk-utkast", archive_id)
    path.write_text("{", encoding="utf-8")
    assert list_archived(tmp_path, "p1", "ovk-utkast") == [
        {"archive_id": archive_id, "olasbar": True}
    ]
    assert client.post(f"{SAVED}/{archive_id}/aterstall").status_code == 409
    assert workflows.load("p1", "ovk-utkast") == record


def test_a_broken_older_copy_is_not_trusted_and_the_work_is_saved_again(tmp_path: Path) -> None:
    record = replace(
        build_record(
            inspection_id="ovk-utkast",
            ovk_object=OvkObject("object-1", "p1", "building-1", "Building"),
            systems=(VentilationSystemRef("FTX01", "FTX", "System FTX01"),),
        ),
        review=(_decision("arbete"),),
    )
    root = tmp_path / "projects" / "p1" / "ovk-utkast-sparade" / "ovk-utkast"
    first = archive(tmp_path, record, "test")
    # Samma innehåll ligger aldrig dubbelt: den nya kopian ersätter den gamla.
    older = root / f"20200101T000000Z-{first[-12:]}.json"
    (root / f"{first}.json").rename(older)
    older.write_text(older.read_text(encoding="utf-8").replace(first, older.stem), encoding="utf-8")
    second = archive(tmp_path, record, "test")
    assert [path.stem for path in root.glob("*.json")] == [second]
    assert load_archived(tmp_path, "p1", "ovk-utkast", second) == record

    # En äldre kopia med samma innehåll som inte går att läsa lämnas kvar,
    # och arbetet sparas i en ny, läsbar kopia.
    broken = root / f"20200101T000000Z-{second[-12:]}.json"
    broken.write_text("{", encoding="utf-8")
    third = archive(tmp_path, record, "test")
    assert load_archived(tmp_path, "p1", "ovk-utkast", third) == record
    assert sorted(path.stem for path in root.glob("*.json")) == sorted({broken.stem, third})


def test_only_the_twenty_latest_copies_are_kept_and_the_latest_is_never_pruned(
    tmp_path: Path,
) -> None:
    base = build_record(
        inspection_id="ovk-utkast",
        ovk_object=OvkObject("object-1", "p1", "building-1", "Building"),
        systems=(VentilationSystemRef("FTX01", "FTX", "System FTX01"),),
    )
    root = tmp_path / "projects" / "p1" / "ovk-utkast-sparade" / "ovk-utkast"
    oldest = replace(base, review=(_decision("äldst"),))
    first = archive(tmp_path, oldest, "test")
    # Den första kopian görs äldst, och tjugo nyare läggs till.
    aged = root / f"20200101T000000Z-{first[-12:]}.json"
    (root / f"{first}.json").rename(aged)
    aged.write_text(aged.read_text(encoding="utf-8").replace(first, aged.stem), encoding="utf-8")
    for index in range(20):
        copy = root / f"2021010{index % 10}T0000{index:02d}Z-{index:012x}.json"
        copy.write_text("{}", encoding="utf-8")
    assert len(list(root.glob("*.json"))) == 21

    # Samma innehåll som den äldsta sparas igen: det är nu det senaste och gallras inte.
    again = archive(tmp_path, oldest, "test")

    remaining = sorted(path.stem for path in root.glob("*.json"))
    assert len(remaining) == 20
    assert again in remaining and aged.stem not in remaining
    assert load_archived(tmp_path, "p1", "ovk-utkast", again) == oldest


def test_record_built_before_this_change_counts_as_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, headers = _prepared(tmp_path, monkeypatch)
    assert client.post(f"{BASE}/protokoll-utkast", headers=headers, json={}).status_code == 200
    # Äldre byggen lämnade ingen notering om hur posten såg ut.
    (tmp_path / "projects" / "p1" / "ovk-field" / "ovk-utkast" / "draft-built.json").unlink()

    refused = client.post(f"{BASE}/protokoll-utkast", headers=headers, json={})

    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "OVK_DRAFT_REPLACE_CONFIRMATION_REQUIRED"
    assert refused.json()["detail"]["summary"]["granskningsbeslut"] == 0


def test_restore_keeps_current_object_and_systems_and_tells_when_field_data_moved_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, headers = _prepared(tmp_path, monkeypatch)
    assert client.post(f"{BASE}/protokoll-utkast", headers=headers, json={}).status_code == 200
    _decide(tmp_path)
    saved = client.post(
        f"{BASE}/protokoll-utkast", headers=headers, json={"confirm_replace": True}
    ).json()["sparat_utkast"]
    workflows = OvkWorkflowRepository(tmp_path)

    # Samma fältunderlag: det återställda utkastet stämmer med protokollkällan.
    same = client.post(f"{SAVED}/{saved}/aterstall")
    assert same.status_code == 200, same.text
    assert same.json()["protokollkalla_aktuell"] is True

    # Objektets namn ändras och fältunderlaget synkas om med en anmärkning till.
    current = workflows.load("p1", "ovk-utkast")
    renamed = replace(current.inspection.ovk_object, name="Nytt namn")
    workflows.save(replace(current, inspection=replace(current.inspection, ovk_object=renamed)))
    snapshot = client.get(f"{BASE}/sync").json()
    payload = snapshot["payload"]
    payload["findings"].append(
        {
            **payload["findings"][0],
            "finding_id": "f2",
            "defect_type": "incorrect_airflow",
            "description": "Kraftigt avvikande flöde",
            "severity": "major",
            "classification": 2,
        }
    )
    resynced = client.put(
        f"{BASE}/sync", json=payload, headers={"X-OVK-Base-Revision": snapshot["snapshot_sha256"]}
    )
    assert resynced.status_code == 200, resynced.text
    rebuilt = client.post(
        f"{BASE}/protokoll-utkast",
        headers={"X-OVK-Base-Revision": resynced.json()["snapshot_sha256"]},
        json={"confirm_replace": True},
    )
    assert rebuilt.status_code == 200, rebuilt.text

    restored = client.post(f"{SAVED}/{saved}/aterstall")

    assert restored.status_code == 200, restored.text
    # Utkastet byggdes från äldre fältunderlag och måste byggas om före utfärdande.
    assert restored.json()["protokollkalla_aktuell"] is False
    back = workflows.load("p1", "ovk-utkast")
    assert back.inspection.ovk_object.name == "Nytt namn"
    assert back.review[0].reviewer == "Stoffe"


def test_issued_inspection_can_be_neither_rebuilt_nor_restored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, headers = _prepared(tmp_path, monkeypatch)
    assert client.post(f"{BASE}/protokoll-utkast", headers=headers, json={}).status_code == 200
    _decide(tmp_path)
    workflows = OvkWorkflowRepository(tmp_path)
    record = workflows.load("p1", "ovk-utkast")
    saved = archive(tmp_path, record, "test")
    # Ett påbörjat utfärdande spärrar besiktningen på samma sätt som ett utfärdat intyg.
    manifest = tmp_path / "projects" / "p1" / "ovk-issuance-manifest" / "ovk-utkast.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")

    for response in (
        client.post(f"{BASE}/protokoll-utkast", headers=headers, json={"confirm_replace": True}),
        client.post(f"{SAVED}/{saved}/aterstall"),
    ):
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "OVK_ISSUANCE_RECOVERY_REQUIRED"
    assert workflows.load("p1", "ovk-utkast") == record
    # Läsning är fortfarande tillåten.
    assert len(client.get(SAVED).json()["sparade"]) == 1
