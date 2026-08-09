from __future__ import annotations

from crow_regulations import reference_by_id

from .defects import defect_type_by_id
from .models import FieldInspectionData


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


def _validate_rule_refs(rule_refs: tuple[str, ...]) -> None:
    for rule_ref in rule_refs:
        reference_by_id(rule_ref)
