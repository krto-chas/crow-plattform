"""Regressionstester för fynden i fältgranskningen (november 2026)."""

from __future__ import annotations

from importlib import resources

from crow_ovk import FindingSeverity
from crow_ovk_field import FieldFinding, FieldInspectionData, FieldRoom, FieldUnit, UnitKind
from crow_ovk_field.models import FieldMeasurement, MeasurePointType, UnitStatus
from crow_ovk_workflow.field_bridge import build_protokoll_utkast
from crow_ovk_workflow.flow_protocol import build_flow_protocol


def _asset(name: str) -> str:
    return resources.files("crow_ovk_module").joinpath("assets", name).read_text(encoding="utf-8")


def _data() -> FieldInspectionData:
    units = (
        FieldUnit(
            unit_id="u1",
            inspection_id="i1",
            number="0004398046511103",
            kind=UnitKind.PREMISES,
            label="Frisör Anna",
            status=UnitStatus.ANMARKNING,
            checked_at="2026-11-17T10:00:00Z",
        ),
        FieldUnit(unit_id="u2", inspection_id="i1", number="7", kind=UnitKind.PREMISES),
        FieldUnit(unit_id="u3", inspection_id="i1", number="1201"),
    )
    rooms = tuple(
        FieldRoom(room_id=f"r{index}", unit_id=f"u{index}", name="WC") for index in (1, 2, 3)
    )
    findings = tuple(
        FieldFinding(
            finding_id=f"f{index}",
            inspection_id="i1",
            unit_id=f"u{index}",
            room_id=f"r{index}",
            defect_type="missing_terminal",
            description="WC: Don saknas",
            severity=FindingSeverity.MINOR,
            classification=1,
        )
        for index in (1, 2, 3)
    )
    measurements = (
        FieldMeasurement(
            measurement_id="m1",
            inspection_id="i1",
            unit_id="u1",
            room_id="r1",
            point_type=MeasurePointType.FRANLUFTSDON,
            point_label="WC 1",
        ),
    )
    return FieldInspectionData(
        inspection_id="i1",
        units=units,
        rooms=rooms,
        findings=findings,
        measurements=measurements,
    )


def test_display_number_uses_label_only_for_named_premises() -> None:
    named, unnamed, apartment = _data().units
    assert named.display_number == "Frisör Anna"
    assert unnamed.display_number == "7"
    assert apartment.display_number == "1201"
    labelled_apartment = FieldUnit(unit_id="u4", inspection_id="i1", number="1301", label="Vind")
    assert labelled_apartment.display_number == "1301"


def test_protocol_rows_show_premises_name_instead_of_internal_number() -> None:
    (row,) = build_protokoll_utkast(_data()).anmarkningar
    assert row.unit_numbers == ("7", "1201", "Frisör Anna")
    assert "0004398046511103" not in row.text


def test_flow_protocol_shows_premises_name() -> None:
    protocol = build_flow_protocol(_data())
    assert "Frisör Anna" in str(protocol)
    assert "0004398046511103" not in str(protocol)


def test_visual_round_always_starts_in_first_room() -> None:
    page = _asset("field.html")
    assert "state.activeRoomId=rooms[0].room_id;" in page
    assert "else if(phase==='visual'){phase='measure';selectRoom(0)}" in page


def test_typed_room_gets_same_preset_terminal_as_room_chip() -> None:
    assert "state.rooms.push(room);\n    addPresetExtract(room);" in _asset("field.html")
    script = _asset("field.js")
    assert "function addPresetExtract(room){" in script
    assert "state.rooms.push(room);addPresetExtract(room);return room}" in script


def test_checked_unit_status_follows_remarks_before_every_local_save() -> None:
    script = _asset("field.js")
    assert "function reconcileUnitStatuses(){" in script
    assert "return;reconcileUnitStatuses();state.dirty=dirty;" in script


def test_server_revision_is_persisted_as_soon_as_it_is_known() -> None:
    script = _asset("field-auth.js")
    assert script.count("await writeDraft(state.dirty);") == 2
    snapshot = script.index("state.last_sync = data.snapshot_sha256;")
    assert script.index("await writeDraft(state.dirty);", snapshot) < script.index(
        "return data;", snapshot
    )


def test_bom_clears_visual_checks_and_progress() -> None:
    script = _asset("field.js")
    assert "state.visual_checks=state.visual_checks.filter(item=>item.unit_id!==unit.unit_id)" in (
        script
    )
    assert "delete state.field_progress[unit.unit_id]" in script


def test_key_times_are_shown_in_local_time() -> None:
    script = _asset("field.js")
    assert "received_at.slice(11,16)" not in script
    assert "localClock(key.received_at)" in script
