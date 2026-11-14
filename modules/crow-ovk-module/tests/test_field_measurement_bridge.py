from decimal import Decimal

import pytest

from crow_ovk import EvidenceOrigin, OvkObject
from crow_ovk_field.models import FieldInspectionData, FieldMeasurement, MeasurePointType
from crow_ovk_workflow import bridge_inspection_inputs, build_protokoll_utkast, build_record


def test_field_measurements_preserve_values_and_identity() -> None:
    obj = OvkObject("f1", "p1", "b1", "Test")
    measured = FieldMeasurement(
        "don-1",
        "i1",
        "u1",
        MeasurePointType.FRANLUFTSDON,
        "Badrum",
        measured_value=Decimal("0"),
        designed_value=Decimal("10.5"),
        system_id="F01",
    )
    pending = FieldMeasurement("don-2", "i1", "u1", MeasurePointType.TILLUFTSDON, "Sovrum")
    unavailable = FieldMeasurement(
        "don-3",
        "i1",
        "u1",
        MeasurePointType.FRANLUFTSDON,
        "Kök",
        measurable=False,
        not_measurable_reason="Ej åtkomligt",
    )
    data = FieldInspectionData("i1", measurements=(measured, pending, unavailable))
    inputs = bridge_inspection_inputs(data, build_protokoll_utkast(data), ovk_object=obj)
    record = build_record(**inputs)  # type: ignore[arg-type]
    (result,) = record.inspection.measurements
    assert result.measurement_id == result.point_id == "don-1"
    assert result.measured_value == Decimal("0")
    assert result.designed_value == Decimal("10.5")
    assert result.deviation_percent == Decimal("-100")
    assert result.system_id == "F01"
    assert result.origin is EvidenceOrigin.MEASURED
    assert result.evidence_ref == "field:i1:measurement:don-1"


def test_nonfinite_measurement_rejected() -> None:
    obj = OvkObject("f1", "p1", "b1", "Test")
    item = FieldMeasurement(
        "don-1",
        "i1",
        "u1",
        MeasurePointType.FRANLUFTSDON,
        "Badrum",
        measured_value=Decimal("NaN"),
    )
    data = FieldInspectionData("i1", measurements=(item,))
    with pytest.raises(ValueError, match="non-finite"):
        bridge_inspection_inputs(data, build_protokoll_utkast(data), ovk_object=obj)
