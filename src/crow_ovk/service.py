from __future__ import annotations

from typing import Any

from .models import (
    ActionStatus,
    CheckStatus,
    InspectionConclusion,
    OvkAction,
    OvkCheckpoint,
    OvkFinding,
    OvkInspection,
    OvkMeasurement,
    OvkObject,
    VentilationSystemRef,
)

SCHEMA_VERSION = "crow-ovk-v0.1"


def build_inspection(
    *,
    inspection_id: str,
    ovk_object: OvkObject,
    systems: tuple[VentilationSystemRef, ...] = (),
    checkpoints: tuple[OvkCheckpoint, ...] = (),
    measurements: tuple[OvkMeasurement, ...] = (),
    findings: tuple[OvkFinding, ...] = (),
    actions: tuple[OvkAction, ...] = (),
) -> OvkInspection:
    _validate_references(systems, checkpoints, measurements, findings, actions)
    conclusion = derive_conclusion(checkpoints, findings, actions)
    return OvkInspection(
        inspection_id=inspection_id,
        ovk_object=ovk_object,
        systems=systems,
        checkpoints=checkpoints,
        measurements=measurements,
        findings=findings,
        actions=actions,
        conclusion=conclusion,
    )


def derive_conclusion(
    checkpoints: tuple[OvkCheckpoint, ...],
    findings: tuple[OvkFinding, ...],
    actions: tuple[OvkAction, ...],
) -> InspectionConclusion:
    if any(checkpoint.status is CheckStatus.NOT_CHECKED for checkpoint in checkpoints):
        return InspectionConclusion.PENDING
    open_action_ids = {
        action.finding_id for action in actions if action.status is ActionStatus.OPEN
    }
    if any(checkpoint.status is CheckStatus.FAIL for checkpoint in checkpoints):
        return InspectionConclusion.DEFICIENCIES
    if any(
        finding.action_required and finding.finding_id in open_action_ids for finding in findings
    ):
        return InspectionConclusion.DEFICIENCIES
    return InspectionConclusion.APPROVED


def inspection_to_payload(inspection: OvkInspection) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "inspection_id": inspection.inspection_id,
        "object": {
            "object_id": inspection.ovk_object.object_id,
            "project_id": inspection.ovk_object.project_id,
            "building_id": inspection.ovk_object.building_id,
            "name": inspection.ovk_object.name,
            "address": inspection.ovk_object.address,
        },
        "systems": [
            {
                "system_id": system.system_id,
                "system_type": system.system_type,
                "label": system.label,
                "source_ref": system.source_ref,
            }
            for system in inspection.systems
        ],
        "checkpoints": [
            {
                "checkpoint_id": checkpoint.checkpoint_id,
                "label": checkpoint.label,
                "status": checkpoint.status.value,
                "system_id": checkpoint.system_id,
                "note": checkpoint.note,
                "origin": checkpoint.origin.value,
                "evidence_ref": checkpoint.evidence_ref,
            }
            for checkpoint in inspection.checkpoints
        ],
        "measurements": [
            _measurement_payload(measurement) for measurement in inspection.measurements
        ],
        "findings": [
            {
                "finding_id": finding.finding_id,
                "description": finding.description,
                "severity": finding.severity.value,
                "checkpoint_id": finding.checkpoint_id,
                "system_id": finding.system_id,
                "action_required": finding.action_required,
                "origin": finding.origin.value,
                "evidence_ref": finding.evidence_ref,
            }
            for finding in inspection.findings
        ],
        "actions": [
            {
                "action_id": action.action_id,
                "finding_id": action.finding_id,
                "description": action.description,
                "status": action.status.value,
            }
            for action in inspection.actions
        ],
        "conclusion": inspection.conclusion.value,
    }


def _measurement_payload(measurement: OvkMeasurement) -> dict[str, Any]:
    deviation = measurement.deviation_percent
    return {
        "measurement_id": measurement.measurement_id,
        "metric": measurement.metric,
        "measured_value": str(measurement.measured_value),
        "designed_value": (
            None if measurement.designed_value is None else str(measurement.designed_value)
        ),
        "deviation_percent": None if deviation is None else str(deviation),
        "unit": measurement.unit,
        "system_id": measurement.system_id,
        "point_id": measurement.point_id,
        "origin": measurement.origin.value,
        "evidence_ref": measurement.evidence_ref,
    }


def _validate_references(
    systems: tuple[VentilationSystemRef, ...],
    checkpoints: tuple[OvkCheckpoint, ...],
    measurements: tuple[OvkMeasurement, ...],
    findings: tuple[OvkFinding, ...],
    actions: tuple[OvkAction, ...],
) -> None:
    system_ids = {system.system_id for system in systems}
    checkpoint_ids = {checkpoint.checkpoint_id for checkpoint in checkpoints}
    finding_ids = {finding.finding_id for finding in findings}

    _ensure_unique("system_id", len(system_ids), len(systems))
    _ensure_unique("checkpoint_id", len(checkpoint_ids), len(checkpoints))
    measurement_ids = {measurement.measurement_id for measurement in measurements}
    _ensure_unique("measurement_id", len(measurement_ids), len(measurements))
    _ensure_unique("finding_id", len(finding_ids), len(findings))
    _ensure_unique("action_id", len({action.action_id for action in actions}), len(actions))

    for checkpoint in checkpoints:
        _validate_system_ref(checkpoint.system_id, system_ids)
    for measurement in measurements:
        _validate_system_ref(measurement.system_id, system_ids)
    for finding in findings:
        _validate_system_ref(finding.system_id, system_ids)
        if finding.checkpoint_id is not None and finding.checkpoint_id not in checkpoint_ids:
            raise ValueError(f"unknown checkpoint_id: {finding.checkpoint_id}")
    for action in actions:
        if action.finding_id not in finding_ids:
            raise ValueError(f"unknown finding_id: {action.finding_id}")


def _validate_system_ref(system_id: str | None, system_ids: set[str]) -> None:
    if system_id is not None and system_id not in system_ids:
        raise ValueError(f"unknown system_id: {system_id}")


def _ensure_unique(name: str, unique_count: int, total_count: int) -> None:
    if unique_count != total_count:
        raise ValueError(f"duplicate {name}")
