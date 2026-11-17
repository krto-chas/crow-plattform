"""Deterministic flow projection; incomplete totals are explicitly marked."""

from collections import defaultdict
from decimal import Decimal
from typing import Any

from crow_ovk_field.models import FieldInspectionData, FieldMeasurement


def _value(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _summary(items: list[FieldMeasurement]) -> dict[str, Any]:
    measured = [item.measured_value for item in items if item.measured_value is not None]
    designed = [item.designed_value for item in items if item.designed_value is not None]
    measured_sum = sum(measured, Decimal(0)) if measured else None
    designed_sum = sum(designed, Decimal(0)) if designed else None
    complete = len(measured) == len(designed) == len(items)
    deviation = None
    if complete and measured_sum is not None and designed_sum:
        deviation = (measured_sum - designed_sum) / designed_sum * Decimal(100)
    return {
        "point_count": len(items),
        "measured_count": len(measured),
        "designed_count": len(designed),
        "pending_count": sum(item.is_pending for item in items),
        "not_measurable_count": sum(not item.measurable for item in items),
        "measured_sum": _value(measured_sum),
        "designed_sum": _value(designed_sum),
        "comparison_complete": complete,
        "deviation_percent": _value(deviation),
    }


def build_flow_protocol(data: FieldInspectionData) -> dict[str, Any]:
    units = {item.unit_id: item for item in data.units}
    rooms = {item.room_id: item for item in data.rooms}
    groups: dict[tuple[str | None, str, str, str], list[FieldMeasurement]] = defaultdict(list)
    systems: dict[tuple[str | None, str, str], list[FieldMeasurement]] = defaultdict(list)
    seen: set[str] = set()
    for item in data.measurements:
        if item.measurement_id in seen or item.inspection_id != data.inspection_id:
            raise ValueError("invalid measurement identity")
        seen.add(item.measurement_id)
        if item.unit_id not in units:
            raise ValueError("measurement references unknown unit")
        if item.room_id is not None:
            room = rooms.get(item.room_id)
            if room is None or room.unit_id != item.unit_id:
                raise ValueError("measurement references invalid room")
        if any(
            value is not None and not value.is_finite()
            for value in (item.measured_value, item.designed_value)
        ):
            raise ValueError("non-finite field measurement")
        key = (item.system_id, item.unit_id, item.point_type.value, item.unit_of_measure)
        groups[key].append(item)
        systems[(item.system_id, item.point_type.value, item.unit_of_measure)].append(item)

    rows = []
    for (system_id, unit_id, direction, unit), items in sorted(
        groups.items(), key=lambda pair: (pair[0][0] or "", *pair[0][1:])
    ):
        points = []
        for item in sorted(items, key=lambda point: point.measurement_id):
            points.append(
                {
                    "measurement_id": item.measurement_id,
                    "room_id": item.room_id,
                    "room_name": rooms[item.room_id].name if item.room_id else None,
                    "point_label": item.point_label,
                    "measured_value": _value(item.measured_value),
                    "designed_value": _value(item.designed_value),
                    "deviation": _value(item.deviation),
                    "status": (
                        "pending"
                        if item.is_pending
                        else "measured"
                        if item.measurable
                        else "not_measurable"
                    ),
                    "reason": item.not_measurable_reason,
                    "finding_id": item.finding_id,
                }
            )
        rows.append(
            {
                "system_id": system_id,
                "unit_id": unit_id,
                "unit_number": units[unit_id].display_number,
                "unit_kind": units[unit_id].kind.value,
                "direction": direction,
                "unit_of_measure": unit,
                "points": points,
                **_summary(items),
            }
        )
    return {
        "inspection_id": data.inspection_id,
        "groups": rows,
        "system_totals": [
            {
                "system_id": system_id,
                "direction": direction,
                "unit_of_measure": unit,
                **_summary(items),
            }
            for (system_id, direction, unit), items in sorted(
                systems.items(), key=lambda pair: (pair[0][0] or "", *pair[0][1:])
            )
        ],
    }
