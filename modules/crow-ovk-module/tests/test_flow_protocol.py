from decimal import Decimal

from crow_ovk_field.models import (
    FieldInspectionData,
    FieldMeasurement,
    FieldUnit,
    MeasurePointType,
)
from crow_ovk_workflow.flow_protocol import build_flow_protocol


def test_flow_totals_separate_systems_directions_and_missing_values() -> None:
    def point(
        identifier: str, system: str, direction: MeasurePointType, value: str | None
    ) -> FieldMeasurement:
        return FieldMeasurement(
            identifier,
            "i1",
            "u1",
            direction,
            identifier,
            measured_value=Decimal(value) if value is not None else None,
            designed_value=Decimal("10"),
            system_id=system,
        )

    data = FieldInspectionData(
        "i1",
        units=(FieldUnit("u1", "i1", "1201"),),
        measurements=(
            point("a", "F01", MeasurePointType.FRANLUFTSDON, "0"),
            point("b", "F01", MeasurePointType.FRANLUFTSDON, None),
            point("c", "F02", MeasurePointType.FRANLUFTSDON, "8"),
            point("d", "F01", MeasurePointType.OVERLUFTSDON, "5"),
        ),
    )
    result = build_flow_protocol(data)
    totals = {
        (row["system_id"], row["direction"]): row for row in result["system_totals"]
    }
    partial = totals[("F01", "franluftsdon")]
    assert partial["measured_sum"] == "0"
    assert partial["designed_sum"] == "20"
    assert partial["pending_count"] == 1
    assert partial["comparison_complete"] is False
    assert partial["deviation_percent"] is None
    assert totals[("F02", "franluftsdon")]["deviation_percent"] == "-20.0"
    assert totals[("F01", "overluftsdon")]["measured_sum"] == "5"
    assert len(result["groups"]) == 3
