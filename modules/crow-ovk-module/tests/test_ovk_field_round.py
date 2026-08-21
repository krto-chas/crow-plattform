from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from crow_ovk import FindingSeverity
from crow_ovk_field import (
    FieldFinding,
    FieldInspectionData,
    FieldMeasurement,
    FieldRoom,
    FieldUnit,
    KeyLog,
    MeasurePointType,
    UnitStatus,
    WindowVentCheck,
    parse_flow_value,
    validate_field_data,
)
from crow_workbench.shell import create_app


def _unit(**overrides: object) -> FieldUnit:
    values: dict[str, object] = {
        "unit_id": "unit-1",
        "inspection_id": "ovk-1",
        "number": "1101",
    }
    values.update(overrides)
    return FieldUnit(**values)  # type: ignore[arg-type]


def test_key_log_requires_timestamps_and_master_note() -> None:
    KeyLog(received=True, received_at="2026-08-10T08:00:00+00:00")
    with pytest.raises(ValueError, match="timestamp"):
        KeyLog(received=True)
    with pytest.raises(ValueError, match="before it was received"):
        KeyLog(returned=True, returned_at="2026-08-10T09:00:00+00:00")
    with pytest.raises(ValueError, match="written note"):
        KeyLog(master_key_used=True)
    KeyLog(master_key_used=True, master_key_note="Förvaltare gav huvudnyckel, boende ej hemma")


def test_unit_status_requires_matching_timestamps() -> None:
    _unit(status=UnitStatus.UA, checked_at="2026-08-10T08:12:00+00:00")
    _unit(status=UnitStatus.BOM, bom_at="2026-08-10T08:12:00+00:00")
    with pytest.raises(ValueError, match="checked_at"):
        _unit(status=UnitStatus.UA)
    with pytest.raises(ValueError, match="bom_at"):
        _unit(status=UnitStatus.BOM)


def test_measurement_rules_and_decimal_parsing() -> None:
    measurement = FieldMeasurement(
        measurement_id="meas-1",
        inspection_id="ovk-1",
        unit_id="unit-1",
        point_type=MeasurePointType.FRANLUFTSDON,
        point_label="Kök 1",
        measured_value=parse_flow_value("34,5"),
        designed_value=Decimal("40"),
    )
    assert measurement.measured_value == Decimal("34.5")
    assert measurement.deviation == Decimal("-5.5")
    # Pass 110b: mätbar punkt utan värde är pågående arbete och tillåten i
    # synkade utkast — kompletthet prövas vid protokollfärdigställandet.
    pending = FieldMeasurement(
        measurement_id="meas-2",
        inspection_id="ovk-1",
        unit_id="unit-1",
        point_type=MeasurePointType.FRANLUFTSDON,
        point_label="Badrum 1",
    )
    assert pending.is_pending
    with pytest.raises(ValueError, match="requires a written reason"):
        FieldMeasurement(
            measurement_id="meas-2b",
            inspection_id="ovk-1",
            unit_id="unit-1",
            point_type=MeasurePointType.FRANLUFTSDON,
            point_label="Badrum 1",
            measurable=False,
        )
    with pytest.raises(ValueError, match="written reason"):
        FieldMeasurement(
            measurement_id="meas-3",
            inspection_id="ovk-1",
            unit_id="unit-1",
            point_type=MeasurePointType.FRANLUFTSDON,
            point_label="Badrum 1",
            measurable=False,
        )
    with pytest.raises(ValueError, match="invalid flow value"):
        parse_flow_value("abc")


def _finding(unit_id: str, severity: FindingSeverity) -> FieldFinding:
    return FieldFinding(
        finding_id="finding-" + severity.value,
        inspection_id="ovk-1",
        unit_id=unit_id,
        defect_type="missing_terminal",
        description="Don saknas",
        severity=severity,
    )


def test_validation_rejects_ua_with_remarks_and_bom_with_data() -> None:
    ua_unit = _unit(status=UnitStatus.UA, checked_at="2026-08-10T08:12:00+00:00")
    data = FieldInspectionData(
        inspection_id="ovk-1",
        units=(ua_unit,),
        findings=(_finding("unit-1", FindingSeverity.MINOR),),
    )
    with pytest.raises(ValueError, match="marked UA"):
        validate_field_data(data)

    info_only = FieldInspectionData(
        inspection_id="ovk-1",
        units=(ua_unit,),
        findings=(_finding("unit-1", FindingSeverity.INFO),),
    )
    validate_field_data(info_only)

    bom_unit = _unit(status=UnitStatus.BOM, bom_at="2026-08-10T08:12:00+00:00")
    bom_with_measurement = FieldInspectionData(
        inspection_id="ovk-1",
        units=(bom_unit,),
        measurements=(
            FieldMeasurement(
                measurement_id="meas-1",
                inspection_id="ovk-1",
                unit_id="unit-1",
                point_type=MeasurePointType.FRANLUFTSDON,
                point_label="Kök 1",
                measured_value=Decimal("30"),
            ),
        ),
    )
    with pytest.raises(ValueError, match="marked bom"):
        validate_field_data(bom_with_measurement)


def test_validation_requires_finding_link_for_not_measurable() -> None:
    unit = _unit()
    room = FieldRoom(room_id="room-1", unit_id="unit-1", name="Badrum")
    finding = FieldFinding(
        finding_id="finding-nm",
        inspection_id="ovk-1",
        unit_id="unit-1",
        defect_type="terminal_not_measurable",
        description="Badrum: don ej mätbart - igenbyggt",
        severity=FindingSeverity.MINOR,
        room_id="room-1",
    )
    orphan = FieldMeasurement(
        measurement_id="meas-1",
        inspection_id="ovk-1",
        unit_id="unit-1",
        point_type=MeasurePointType.FRANLUFTSDON,
        point_label="Badrum 1",
        room_id="room-1",
        measurable=False,
        not_measurable_reason="igenbyggt",
    )
    with pytest.raises(ValueError, match="linked finding"):
        validate_field_data(
            FieldInspectionData(
                inspection_id="ovk-1",
                units=(unit,),
                rooms=(room,),
                measurements=(orphan,),
            )
        )
    linked = FieldMeasurement(
        measurement_id="meas-1",
        inspection_id="ovk-1",
        unit_id="unit-1",
        point_type=MeasurePointType.FRANLUFTSDON,
        point_label="Badrum 1",
        room_id="room-1",
        measurable=False,
        not_measurable_reason="igenbyggt",
        finding_id="finding-nm",
    )
    validate_field_data(
        FieldInspectionData(
            inspection_id="ovk-1",
            units=(unit,),
            rooms=(room,),
            findings=(finding,),
            measurements=(linked,),
        )
    )


def test_window_vent_check_references_are_validated() -> None:
    unit = _unit()
    check = WindowVentCheck(check_id="wv-1", inspection_id="ovk-1", unit_id="unit-1", present=True)
    validate_field_data(
        FieldInspectionData(inspection_id="ovk-1", units=(unit,), window_vents=(check,))
    )
    stray = WindowVentCheck(check_id="wv-2", inspection_id="ovk-1", unit_id="unit-9", present=False)
    with pytest.raises(ValueError, match="unknown unit"):
        validate_field_data(
            FieldInspectionData(inspection_id="ovk-1", units=(unit,), window_vents=(stray,))
        )


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


def _round_payload() -> dict[str, object]:
    return {
        "inspection_id": "ovk-1",
        "units": [
            {
                "unit_id": "unit-1",
                "number": "1101",
                "kind": "apartment",
                "status": "ua",
                "checked_at": "2026-08-10T08:12:00+00:00",
                "key": {
                    "received": True,
                    "received_at": "2026-08-10T08:05:00+00:00",
                    "returned": True,
                    "returned_at": "2026-08-10T08:20:00+00:00",
                    "master_key_used": False,
                    "master_key_note": "",
                },
            },
            {
                "unit_id": "unit-2",
                "number": "1102",
                "kind": "apartment",
                "status": "bom",
                "bom_at": "2026-08-10T08:25:00+00:00",
                "bom_note": "Ingen öppnade",
            },
        ],
        "rooms": [{"room_id": "room-1", "unit_id": "unit-1", "name": "Kök"}],
        "findings": [],
        "photos": [],
        "measurements": [
            {
                "measurement_id": "meas-1",
                "unit_id": "unit-1",
                "point_type": "franluftsdon",
                "point_label": "Kök 1",
                "room_id": "room-1",
                "measurable": True,
                "measured_value": "34,5",
                "designed_value": "40",
            }
        ],
        "window_vents": [
            {"check_id": "wv-1", "unit_id": "unit-1", "room_id": "room-1", "present": True}
        ],
    }


def test_surface_sync_roundtrip_preserves_round_data(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.put("/api/ovk/field/sync/ovk-1", json=_round_payload())
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["measurements"] == 1
    assert summary["window_vents"] == 1
    assert summary["unit_status_counts"] == {
        "ej_paborjad": 0,
        "ua": 1,
        "anmarkning": 0,
        "bom": 1,
    }
    assert summary["coverage_complete"] is True

    stored = client.get("/api/ovk/field/sync/ovk-1")
    assert stored.status_code == 200
    payload = stored.json()["payload"]
    assert payload["measurements"][0]["measured_value"] == "34.5"
    assert payload["units"][0]["key"]["returned"] is True
    assert payload["units"][1]["status"] == "bom"
    assert payload["units"][1]["bom_at"] == "2026-08-10T08:25:00+00:00"


def test_surface_rejects_ua_unit_with_remark(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    payload = _round_payload()
    payload["findings"] = [
        {
            "finding_id": "finding-1",
            "unit_id": "unit-1",
            "defect_type": "missing_terminal",
            "description": "Kök: don saknas",
            "severity": "minor",
            "room_id": "room-1",
        }
    ]
    response = client.put("/api/ovk/field/sync/ovk-1", json=payload)
    assert response.status_code == 422
    assert "marked UA" in response.json()["detail"]["message"]


def test_context_accepts_and_validates_system_type(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    saved = client.put(
        "/api/ovk/field/context/ovk-1",
        json={"project_id": "p1", "inspector": "Stoffe", "system_type": "ftx"},
    )
    assert saved.status_code == 200
    assert saved.json()["system_type"] == "FTX"
    invalid = client.put(
        "/api/ovk/field/context/ovk-1",
        json={"project_id": "p1", "inspector": "Stoffe", "system_type": "XYZ"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "INVALID_OVK_FIELD_SYSTEM_TYPE"
