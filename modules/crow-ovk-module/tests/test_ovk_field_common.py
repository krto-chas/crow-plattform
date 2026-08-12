from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from crow_ovk import CheckStatus
from crow_ovk_field import (
    FieldCheckpoint,
    FieldInspectionData,
    OvkPhotoEvidence,
    TechnicalSpace,
    TechnicalSpaceKind,
    load_checklists,
    nameplate_missing_spaces,
    validate_field_data,
)
from crow_workbench.shell import create_app

_SHA = "a" * 64


def _space(space_id: str = "space-1") -> TechnicalSpace:
    return TechnicalSpace(
        space_id=space_id,
        inspection_id="ovk-1",
        kind=TechnicalSpaceKind.FLAKTRUM,
        label="Fläktrum plan 10, LB01",
        location="Plan 10",
    )


def _nameplate_photo(space_id: str = "space-1") -> OvkPhotoEvidence:
    return OvkPhotoEvidence(
        photo_id="photo-1",
        inspection_id="ovk-1",
        unit_id="",
        unit_number="",
        defect_type="equipment_nameplate",
        captured_at="2026-08-10T09:00:00+00:00",
        captured_by="Stoffe",
        local_uri="indexeddb:skylt.jpg",
        sha256=_SHA,
        mime_type="image/jpeg",
        space_id=space_id,
    )


def test_checklist_templates_load_for_both_space_kinds() -> None:
    checklists = load_checklists()
    assert len(checklists[TechnicalSpaceKind.FLAKTRUM]) == 10
    assert len(checklists[TechnicalSpaceKind.TAKFLAKT]) == 6
    labels = [item.label for item in checklists[TechnicalSpaceKind.TAKFLAKT]]
    assert any("Säkerhetsbrytare" in label for label in labels)


def test_checkpoint_without_comment_is_ua_and_fail_requires_note() -> None:
    checkpoint = FieldCheckpoint(
        checkpoint_id="cp-1",
        inspection_id="ovk-1",
        space_id="space-1",
        label="Filter – skick och montage",
    )
    assert checkpoint.status is CheckStatus.PASS
    with pytest.raises(ValueError, match="written note"):
        FieldCheckpoint(
            checkpoint_id="cp-2",
            inspection_id="ovk-1",
            space_id="space-1",
            label="Fläktdrift",
            status=CheckStatus.FAIL,
        )
    FieldCheckpoint(
        checkpoint_id="cp-2",
        inspection_id="ovk-1",
        space_id="space-1",
        label="Fläktdrift",
        status=CheckStatus.FAIL,
        note="Kraftig vibration vid drift",
    )


def test_photo_requires_unit_or_space_binding() -> None:
    _nameplate_photo()
    with pytest.raises(ValueError, match="unit binding or a technical space"):
        OvkPhotoEvidence(
            photo_id="photo-2",
            inspection_id="ovk-1",
            unit_id="",
            unit_number="",
            defect_type="equipment_nameplate",
            captured_at="2026-08-10T09:00:00+00:00",
            captured_by="Stoffe",
            local_uri="indexeddb:skylt.jpg",
            sha256=_SHA,
            mime_type="image/jpeg",
        )


def test_validation_checks_space_references_and_nameplate_coverage() -> None:
    data = FieldInspectionData(
        inspection_id="ovk-1",
        technical_spaces=(_space(),),
        checkpoints=(
            FieldCheckpoint(
                checkpoint_id="cp-1",
                inspection_id="ovk-1",
                space_id="space-1",
                label="Filter",
            ),
        ),
        photos=(_nameplate_photo(),),
    )
    validate_field_data(data)
    assert nameplate_missing_spaces(data) == ()

    undocumented = FieldInspectionData(inspection_id="ovk-1", technical_spaces=(_space("space-2"),))
    assert nameplate_missing_spaces(undocumented) == ("space-2",)

    stray_checkpoint = FieldInspectionData(
        inspection_id="ovk-1",
        technical_spaces=(_space(),),
        checkpoints=(
            FieldCheckpoint(
                checkpoint_id="cp-9",
                inspection_id="ovk-1",
                space_id="space-9",
                label="Filter",
            ),
        ),
    )
    with pytest.raises(ValueError, match="unknown technical space"):
        validate_field_data(stray_checkpoint)

    stray_photo = FieldInspectionData(inspection_id="ovk-1", photos=(_nameplate_photo("space-9"),))
    with pytest.raises(ValueError, match="unknown technical space"):
        validate_field_data(stray_photo)


def _write_entitlements(root: Path) -> None:
    target = root / "config" / "customers" / "acme"
    target.mkdir(parents=True, exist_ok=True)
    (target / "entitlements.json").write_text(
        json.dumps({"customer_id": "acme", "modules": [{"id": "ovk", "active": True}]}),
        encoding="utf-8",
    )


def _client(tmp_path: Path, monkeypatch: MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    _write_entitlements(tmp_path)
    return TestClient(create_app(tmp_path))


def test_surface_serves_checklists(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get("/api/ovk/field/checklists")
    assert response.status_code == 200
    payload = response.json()["checklists"]
    assert len(payload["flaktrum"]) == 10
    assert len(payload["takflakt"]) == 6


def test_surface_sync_roundtrip_with_technical_spaces(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    payload = {
        "inspection_id": "ovk-1",
        "units": [],
        "rooms": [],
        "findings": [],
        "photos": [
            {
                "photo_id": "photo-1",
                "defect_type": "equipment_nameplate",
                "captured_at": "2026-08-10T09:00:00+00:00",
                "captured_by": "Stoffe",
                "local_uri": "indexeddb:skylt.jpg",
                "sha256": _SHA,
                "mime_type": "image/jpeg",
                "space_id": "space-1",
                "description": "Märkskylt · LB01",
            }
        ],
        "technical_spaces": [
            {
                "space_id": "space-1",
                "kind": "flaktrum",
                "label": "Fläktrum plan 10, LB01",
                "location": "Plan 10",
            },
            {
                "space_id": "space-2",
                "kind": "takflakt",
                "label": "Takfläkt hus A, FF01",
                "location": "Tak",
            },
        ],
        "checkpoints": [
            {
                "checkpoint_id": "cp-1",
                "space_id": "space-1",
                "label": "Filter – skick och montage",
            },
            {
                "checkpoint_id": "cp-2",
                "space_id": "space-2",
                "label": "Säkerhetsbrytare – finns och fungerar",
                "status": "fail",
                "note": "Säkerhetsbrytare saknas vid fläkten",
            },
        ],
    }
    response = client.put("/api/ovk/field/sync/ovk-1", json=payload)
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["technical_spaces"] == 2
    assert summary["checkpoints"] == 2
    assert summary["checkpoint_failures"] == 1
    assert summary["nameplates_missing"] == ["space-2"]

    stored = client.get("/api/ovk/field/sync/ovk-1").json()["payload"]
    assert stored["checkpoints"][0]["status"] == "pass"
    assert stored["checkpoints"][1]["note"] == "Säkerhetsbrytare saknas vid fläkten"
    assert stored["photos"][0]["space_id"] == "space-1"


def test_surface_rejects_failed_checkpoint_without_note(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    payload = {
        "inspection_id": "ovk-1",
        "technical_spaces": [{"space_id": "space-1", "kind": "flaktrum", "label": "Fläktrum LB01"}],
        "checkpoints": [
            {
                "checkpoint_id": "cp-1",
                "space_id": "space-1",
                "label": "Filter",
                "status": "fail",
            }
        ],
    }
    response = client.put("/api/ovk/field/sync/ovk-1", json=payload)
    assert response.status_code == 422
    assert "written note" in response.json()["detail"]["message"]
