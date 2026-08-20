"""Pass 110: protokollbryggan — fältsnapshot till protokollutkast."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_ovk_workflow import _client, _workflow_payload  # noqa: F401  (fixture-mönster)

from crow_ovk_field import default_position_for, load_positions, position_by_id
from crow_ovk_field.models import (
    FieldFinding,
    FieldInspectionData,
    FieldRoom,
    FieldUnit,
    TechnicalSpace,
    TechnicalSpaceKind,
)
from crow_ovk_workflow import Besiktningsresultat, build_protokoll_utkast


def _data(*findings: FieldFinding) -> FieldInspectionData:
    units = (
        FieldUnit(unit_id="u1", inspection_id="ovk-b", number="1201"),
        FieldUnit(unit_id="u2", inspection_id="ovk-b", number="1202"),
        FieldUnit(unit_id="u3", inspection_id="ovk-b", number="1501"),
    )
    rooms = (
        FieldRoom(room_id="r1", unit_id="u1", name="Badrum"),
        FieldRoom(room_id="r2", unit_id="u2", name="Badrum"),
        FieldRoom(room_id="r3", unit_id="u3", name="Badrum"),
    )
    spaces = (
        TechnicalSpace(
            space_id="ts1",
            inspection_id="ovk-b",
            kind=TechnicalSpaceKind.FLAKTRUM,
            label="LB01",
        ),
    )
    return FieldInspectionData(
        inspection_id="ovk-b",
        units=units,
        rooms=rooms,
        findings=findings,
        technical_spaces=spaces,
    )


def _finding(finding_id: str, unit_id: str, room_id: str, classification: int) -> FieldFinding:
    return FieldFinding(
        finding_id=finding_id,
        inspection_id="ovk-b",
        unit_id=unit_id,
        defect_type="contaminated_extract_terminal",
        description="Skitig ventil i bad",
        room_id=room_id,
        classification=classification,
    )


def test_positions_lexicon_loads_full_taxonomy() -> None:
    positions = load_positions()
    assert len(positions) == 31
    assert position_by_id("2.7").label == "Don"
    assert position_by_id("4.4").group_label == "Klimat"
    default = default_position_for("contaminated_extract_terminal")
    assert default is not None and default.position_id == "2.7"
    assert default_position_for("okand_typ") is None


def test_same_defect_same_room_groups_units_in_template_format() -> None:
    utkast = build_protokoll_utkast(
        _data(
            _finding("f1", "u1", "r1", 1),
            _finding("f2", "u2", "r2", 1),
            _finding("f3", "u3", "r3", 1),
        )
    )
    assert len(utkast.anmarkningar) == 1
    row = utkast.anmarkningar[0]
    assert row.text == "Smutsigt frånluftsdon – Badrum: 1201, 1202, 1501"
    assert row.pos == "2.7"
    assert row.unit_numbers == ("1201", "1202", "1501")
    assert utkast.besiktningsresultat == Besiktningsresultat.GODKAND_MED_ANMARKNING


def test_result_derivation_is_deterministic() -> None:
    assert build_protokoll_utkast(_data()).besiktningsresultat == Besiktningsresultat.GODKAND

    only_info = build_protokoll_utkast(_data(_finding("f1", "u1", "r1", 0)))
    assert only_info.besiktningsresultat == Besiktningsresultat.GODKAND
    assert len(only_info.upplysningar) == 1 and not only_info.anmarkningar

    with_eg = build_protokoll_utkast(
        _data(_finding("f1", "u1", "r1", 1), _finding("f2", "u2", "r2", 2))
    )
    assert with_eg.besiktningsresultat == Besiktningsresultat.EJ_GODKAND
    # Klass 2 sorteras först.
    assert with_eg.anmarkningar[0].classification == 2


def test_suggested_coverage_from_technical_spaces() -> None:
    utkast = build_protokoll_utkast(_data())
    coverage = utkast.suggested_coverage
    assert [item.label for item in coverage.aggregat] == ["LB01"]
    # Förslaget bär ingen bekräftelse: STATED-steget förblir manuellt.
    assert coverage.system_list_confirmation is None


def test_protokoll_utkast_endpoint_builds_record_from_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client: TestClient = _client(tmp_path, monkeypatch)
    snapshot = {
        "inspection_id": "ovk-brygga",
        "system_type": "FTX",
        "units": [
            {
                "unit_id": "u1",
                "number": "1201",
                "kind": "apartment",
                "status": "anmarkning",
                "checked_at": "2026-08-20T10:00:00+02:00",
            },
            {
                "unit_id": "u2",
                "number": "1202",
                "kind": "apartment",
                "status": "anmarkning",
                "checked_at": "2026-08-20T10:30:00+02:00",
            },
        ],
        "rooms": [
            {"room_id": "r1", "unit_id": "u1", "name": "Badrum"},
            {"room_id": "r2", "unit_id": "u2", "name": "Badrum"},
        ],
        "findings": [
            {
                "finding_id": "f1",
                "unit_id": "u1",
                "room_id": "r1",
                "defect_type": "contaminated_extract_terminal",
                "description": "Skitig ventil i bad",
                "severity": "minor",
                "classification": 1,
            },
            {
                "finding_id": "f2",
                "unit_id": "u2",
                "room_id": "r2",
                "defect_type": "incorrect_airflow",
                "description": "Kraftigt avvikande flöde",
                "severity": "major",
                "classification": 2,
            },
        ],
        "technical_spaces": [
            {"space_id": "ts1", "kind": "flaktrum", "label": "LB01", "location": "Vind"}
        ],
    }
    saved = client.put("/api/ovk/field/sync/ovk-brygga", json=snapshot)
    assert saved.status_code == 200, saved.text

    response = client.post("/api/ovk/projects/p1/field/ovk-brygga/protokoll-utkast", json={})
    assert response.status_code == 200, response.text
    body = response.json()
    utkast = body["utkast"]
    assert utkast["besiktningsresultat"] == "ej_godkand"
    texts = [row["text"] for row in utkast["anmarkningar"]]
    assert "Smutsigt frånluftsdon – Badrum: 1201" in texts
    assert any("avvikande" in text.lower() or "flöde" in text.lower() for text in texts)
    # Klass 2-raden först och med positionskod 3.7 (Luftflöden).
    assert utkast["anmarkningar"][0]["classification"] == 2
    assert utkast["anmarkningar"][0]["pos"] == "3.7"

    record = body["record"]
    # EG: åtgärd öppen → deficiencies; utkastet är inte protokollklart förrän
    # systemförteckningen bekräftats (STATED) — täckningsgrinden från pass 101.
    assert record["inspection"]["conclusion"] == "deficiencies"
    assert record["coverage_complete"] is True
    assert record["coverage"]["fastighetsniva"] == "systemforteckning_ej_bekraftad"

    missing = client.post("/api/ovk/projects/p1/field/saknas/protokoll-utkast", json={})
    assert missing.status_code == 404
