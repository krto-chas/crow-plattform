from __future__ import annotations

from crow_ovk import FindingSeverity
from crow_regulations import reference_by_id

from .defects import defect_type_by_id
from .models import FieldInspectionData, UnitStatus


def validate_field_data(data: FieldInspectionData) -> None:
    unit_ids = {item.unit_id for item in data.units}
    room_ids = {item.room_id for item in data.rooms}
    finding_ids = {item.finding_id for item in data.findings}

    if len(unit_ids) != len(data.units):
        raise ValueError("duplicate field unit ids")
    if len(room_ids) != len(data.rooms):
        raise ValueError("duplicate field room ids")
    if len(finding_ids) != len(data.findings):
        raise ValueError("duplicate field finding ids")

    for room in data.rooms:
        if room.unit_id not in unit_ids:
            raise ValueError(f"room {room.room_id!r} references unknown unit {room.unit_id!r}")

    for finding in data.findings:
        if finding.unit_id not in unit_ids:
            raise ValueError(f"finding {finding.finding_id!r} references unknown unit")
        if finding.room_id is not None and finding.room_id not in room_ids:
            raise ValueError(f"finding {finding.finding_id!r} references unknown room")
        defect_type_by_id(finding.defect_type)
        _validate_rule_refs(finding.rule_refs)

    photo_ids: set[str] = set()
    units_by_id = {item.unit_id: item for item in data.units}
    for photo in data.photos:
        if photo.photo_id in photo_ids:
            raise ValueError(f"duplicate photo id {photo.photo_id!r}")
        photo_ids.add(photo.photo_id)
        if photo.space_id is not None:
            if photo.space_id not in {item.space_id for item in data.technical_spaces}:
                raise ValueError(f"photo {photo.photo_id!r} references unknown technical space")
        else:
            unit = units_by_id.get(photo.unit_id)
            if unit is None:
                raise ValueError(f"photo {photo.photo_id!r} references unknown unit")
            if photo.unit_number != unit.number:
                raise ValueError(f"photo {photo.photo_id!r} unit_number does not match field unit")
        if photo.room_id is not None and photo.room_id not in room_ids:
            raise ValueError(f"photo {photo.photo_id!r} references unknown room")
        if photo.finding_id is not None and photo.finding_id not in finding_ids:
            raise ValueError(f"photo {photo.photo_id!r} references unknown finding")
        defect_type_by_id(photo.defect_type)
        _validate_rule_refs(photo.rule_refs)

    _validate_measurements(data)
    _validate_window_vents(data)
    _validate_technical_spaces(data)
    _validate_status_consistency(data)


def _validate_status_consistency(data: FieldInspectionData) -> None:
    findings_by_unit: dict[str, int] = {}
    for finding in data.findings:
        if finding.severity in (FindingSeverity.MINOR, FindingSeverity.MAJOR):
            findings_by_unit[finding.unit_id] = findings_by_unit.get(finding.unit_id, 0) + 1
    measured_units = {item.unit_id for item in data.measurements}
    for unit in data.units:
        remark_count = findings_by_unit.get(unit.unit_id, 0)
        if unit.status is UnitStatus.UA and remark_count:
            raise ValueError(f"unit {unit.number!r} is marked UA but has {remark_count} remark(s)")
        if unit.status is UnitStatus.BOM and (remark_count or unit.unit_id in measured_units):
            raise ValueError(
                f"unit {unit.number!r} is marked bom but carries findings or measurements"
            )


def _validate_measurements(data: FieldInspectionData) -> None:
    unit_ids = {item.unit_id for item in data.units}
    room_ids = {item.room_id for item in data.rooms}
    finding_ids = {item.finding_id for item in data.findings}
    seen: set[str] = set()
    for measurement in data.measurements:
        if measurement.measurement_id in seen:
            raise ValueError(f"duplicate measurement id {measurement.measurement_id!r}")
        seen.add(measurement.measurement_id)
        if measurement.unit_id not in unit_ids:
            raise ValueError(f"measurement {measurement.measurement_id!r} references unknown unit")
        if measurement.room_id is not None and measurement.room_id not in room_ids:
            raise ValueError(f"measurement {measurement.measurement_id!r} references unknown room")
        if measurement.finding_id is not None and measurement.finding_id not in finding_ids:
            raise ValueError(
                f"measurement {measurement.measurement_id!r} references unknown finding"
            )
        if not measurement.measurable and measurement.finding_id is None:
            raise ValueError(
                f"not measurable point {measurement.measurement_id!r} requires a linked finding"
            )


def _validate_window_vents(data: FieldInspectionData) -> None:
    unit_ids = {item.unit_id for item in data.units}
    room_ids = {item.room_id for item in data.rooms}
    seen: set[str] = set()
    for check in data.window_vents:
        if check.check_id in seen:
            raise ValueError(f"duplicate window vent check id {check.check_id!r}")
        seen.add(check.check_id)
        if check.unit_id not in unit_ids:
            raise ValueError(f"window vent check {check.check_id!r} references unknown unit")
        if check.room_id is not None and check.room_id not in room_ids:
            raise ValueError(f"window vent check {check.check_id!r} references unknown room")


def _validate_technical_spaces(data: FieldInspectionData) -> None:
    space_ids: set[str] = set()
    for space in data.technical_spaces:
        if space.space_id in space_ids:
            raise ValueError(f"duplicate technical space id {space.space_id!r}")
        space_ids.add(space.space_id)
    checkpoint_ids: set[str] = set()
    for checkpoint in data.checkpoints:
        if checkpoint.checkpoint_id in checkpoint_ids:
            raise ValueError(f"duplicate checkpoint id {checkpoint.checkpoint_id!r}")
        checkpoint_ids.add(checkpoint.checkpoint_id)
        if checkpoint.space_id not in space_ids:
            raise ValueError(
                f"checkpoint {checkpoint.checkpoint_id!r} references unknown technical space"
            )


def nameplate_missing_spaces(data: FieldInspectionData) -> tuple[str, ...]:
    """Utrymmen som ännu saknar dokumenterad märkskylt (foto)."""

    documented = {
        photo.space_id
        for photo in data.photos
        if photo.space_id is not None and photo.defect_type == "equipment_nameplate"
    }
    return tuple(
        space.space_id for space in data.technical_spaces if space.space_id not in documented
    )


def _validate_rule_refs(rule_refs: tuple[str, ...]) -> None:
    for rule_ref in rule_refs:
        reference_by_id(rule_ref)
