from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import crow_ovk
from crow_ovk import CheckStatus, OvkCheckpoint, OvkMeasurement, OvkObject, build_inspection


def test_crow_ovk_is_owned_by_first_party_module() -> None:
    package_file = Path(crow_ovk.__file__).resolve()
    normalized = package_file.as_posix()

    assert "/modules/crow-ovk-module/src/crow_ovk/" in normalized
    assert "/src/crow_ovk/" not in normalized.replace(
        "/modules/crow-ovk-module/src/crow_ovk/", ""
    )


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
