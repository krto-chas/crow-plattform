from decimal import Decimal

import pytest

from crow_ovk import (
    ActionStatus,
    CheckStatus,
    EvidenceOrigin,
    FindingSeverity,
    InspectionConclusion,
    OvkAction,
    OvkCheckpoint,
    OvkFinding,
    OvkMeasurement,
    OvkObject,
    VentilationSystemRef,
    build_inspection,
    inspection_to_payload,
)


def _object() -> OvkObject:
    return OvkObject(
        object_id="obj-1",
        project_id="project-1",
        building_id="building-1",
        name="Testfastighet",
        address="Testgatan 1",
    )


def _system() -> VentilationSystemRef:
    return VentilationSystemRef(system_id="FTX01", system_type="FTX", label="FTX01")


def test_measurement_deviation_is_transparent_and_not_a_pass_fail_rule() -> None:
    measurement = OvkMeasurement(
        measurement_id="m1",
        metric="airflow",
        designed_value=Decimal("100"),
        measured_value=Decimal("85"),
        unit="l/s",
        system_id="FTX01",
    )
    assert measurement.deviation_percent == Decimal("-15.00")


def test_pending_when_checkpoint_is_not_checked() -> None:
    inspection = build_inspection(
        inspection_id="ovk-1",
        ovk_object=_object(),
        systems=(_system(),),
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="c1",
                label="Kontrollera funktion",
                status=CheckStatus.NOT_CHECKED,
                system_id="FTX01",
            ),
        ),
    )
    assert inspection.conclusion is InspectionConclusion.PENDING


def test_failed_checkpoint_gives_deficiencies() -> None:
    inspection = build_inspection(
        inspection_id="ovk-1",
        ovk_object=_object(),
        systems=(_system(),),
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="c1",
                label="Kontrollera funktion",
                status=CheckStatus.FAIL,
                system_id="FTX01",
            ),
        ),
    )
    assert inspection.conclusion is InspectionConclusion.DEFICIENCIES


def test_open_required_action_gives_deficiencies() -> None:
    finding = OvkFinding(
        finding_id="f1",
        description="Filterbyte krävs",
        severity=FindingSeverity.MINOR,
        system_id="FTX01",
        origin=EvidenceOrigin.OBSERVED,
    )
    inspection = build_inspection(
        inspection_id="ovk-1",
        ovk_object=_object(),
        systems=(_system(),),
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="c1",
                label="Kontrollera funktion",
                status=CheckStatus.PASS,
                system_id="FTX01",
            ),
        ),
        findings=(finding,),
        actions=(
            OvkAction(
                action_id="a1",
                finding_id="f1",
                description="Byt filter",
                status=ActionStatus.OPEN,
            ),
        ),
    )
    assert inspection.conclusion is InspectionConclusion.DEFICIENCIES


def test_all_checked_without_open_required_findings_is_approved() -> None:
    inspection = build_inspection(
        inspection_id="ovk-1",
        ovk_object=_object(),
        systems=(_system(),),
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="c1",
                label="Kontrollera funktion",
                status=CheckStatus.PASS,
                system_id="FTX01",
            ),
        ),
    )
    assert inspection.conclusion is InspectionConclusion.APPROVED


def test_unknown_system_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown system_id"):
        build_inspection(
            inspection_id="ovk-1",
            ovk_object=_object(),
            systems=(_system(),),
            measurements=(
                OvkMeasurement(
                    measurement_id="m1",
                    metric="airflow",
                    measured_value=Decimal("100"),
                    unit="l/s",
                    system_id="UNKNOWN",
                ),
            ),
        )


def test_payload_serializes_decimal_values_as_strings() -> None:
    inspection = build_inspection(
        inspection_id="ovk-1",
        ovk_object=_object(),
        systems=(_system(),),
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="c1",
                label="Kontrollera funktion",
                status=CheckStatus.PASS,
                system_id="FTX01",
            ),
        ),
        measurements=(
            OvkMeasurement(
                measurement_id="m1",
                metric="airflow",
                designed_value=Decimal("100"),
                measured_value=Decimal("95"),
                unit="l/s",
                system_id="FTX01",
                evidence_ref="field:m1",
            ),
        ),
    )
    payload = inspection_to_payload(inspection)
    measurement = payload["measurements"][0]
    assert measurement["measured_value"] == "95"
    assert measurement["designed_value"] == "100"
    assert measurement["deviation_percent"] == "-5.00"
    assert measurement["evidence_ref"] == "field:m1"
