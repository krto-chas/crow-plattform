from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import crow_ovk
import crow_ovk_field
import crow_ovk_workflow
from crow_ovk import CheckStatus, OvkCheckpoint, OvkMeasurement, OvkObject, build_inspection
from crow_ovk_field import FieldInspectionData, FieldUnit, defect_type_by_id, validate_field_data
from crow_ovk_workflow import build_record, record_to_payload


def _module_path(package_file: str | None) -> str:
    assert package_file is not None
    return Path(package_file).resolve().as_posix()


def test_ovk_packages_are_owned_by_first_party_module() -> None:
    for package_name, package_file in (
        ("crow_ovk", crow_ovk.__file__),
        ("crow_ovk_field", crow_ovk_field.__file__),
        ("crow_ovk_workflow", crow_ovk_workflow.__file__),
    ):
        normalized = _module_path(package_file)
        expected = f"/modules/crow-ovk-module/src/{package_name}/"
        assert expected in normalized
        assert f"/src/{package_name}/" not in normalized.replace(expected, "")


def test_relocated_ovk_core_preserves_public_behavior() -> None:
    inspection = build_inspection(
        inspection_id="inspection-1",
        ovk_object=OvkObject(
            object_id="object-1",
            project_id="project-1",
            building_id="building-1",
            name="Testobjekt",
        ),
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="checkpoint-1",
                label="Kontrollpunkt",
                status=CheckStatus.PASS,
            ),
        ),
        measurements=(
            OvkMeasurement(
                measurement_id="measurement-1",
                metric="airflow",
                measured_value=Decimal("95"),
                designed_value=Decimal("100"),
                unit="l/s",
            ),
        ),
    )
    assert inspection.conclusion.value == "approved"
    assert inspection.measurements[0].deviation_percent == Decimal("-5.00")


def test_relocated_field_package_keeps_lexicon_and_validation() -> None:
    assert defect_type_by_id("blocked_terminal").label == "Blockerat don"
    validate_field_data(
        FieldInspectionData(
            inspection_id="inspection-1",
            units=(FieldUnit("unit-1", "inspection-1", "1203"),),
        )
    )


def test_relocated_workflow_preserves_serialization() -> None:
    record = build_record(
        inspection_id="inspection-1",
        ovk_object=OvkObject(
            object_id="object-1",
            project_id="project-1",
            building_id="building-1",
            name="Testobjekt",
        ),
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="checkpoint-1",
                label="Kontrollpunkt",
                status=CheckStatus.PASS,
            ),
        ),
    )
    payload = record_to_payload(record)
    assert payload["inspection"]["inspection_id"] == "inspection-1"
    assert payload["protocol_ready"] is True
