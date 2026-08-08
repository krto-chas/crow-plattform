from __future__ import annotations

from decimal import Decimal
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
    if any(item.status is CheckStatus.NOT_CHECKED for item in checkpoints):
        return InspectionConclusion.PENDING
    open_action_ids = {item.finding_id for item in actions if item.status is ActionStatus.OPEN}
    if any(item.status is CheckStatus.FAIL for item in checkpoints):
        return InspectionConclusion.DEFICIENCIES
    if any(item.action_required and item.finding_id in open_action_ids for item in findings):
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
                "system_id": item.system_id,
                "system_type": item.system_type,
                "label": item.label,
                "source_ref": item.source_ref,
            }
            for item in inspection.systems
        ],
        "checkpoints": [
            {
                "checkpoint_id": item.checkpoint_id,
                "label": item.label,
                "status": item.status.value,
                "system_id": item.system_id,
                "note": item.note,
                "origin": item.origin.value,
                "evidence_ref": item.evidence_ref,
            }
            for item in inspection.checkpoints
        ],
        "measurements": [_measurement_payload(item) for item in inspection.measurements],
        "findings": [
            {
                "finding_id": item.finding_id,
                "description": item.description,
                "severity": item.severity.value,
                "checkpoint_id": item.checkpoint_id,
                "system_id": item.system_id,
                "action_required": item.action_required,
                "origin": item.origin.value,
                "evidence_ref": item.evidence_ref,
            }
            for item in inspection.findings
        ],
        "actions": [
            {
                "action_id": item.action_id,
                "finding_id": item.finding_id,
                "description": item.description,
                "status": item.status.value,
            }
            for item in inspection.actions
        ],
        "conclusion": inspection.conclusion.value,
    }


def _measurement_payload(item: OvkMeasurement) -> dict[str, Any]:
    deviation = item.deviation_percent
    return {
        "measurement_id": item.measurement_id,
        "metric": item.metric,
        "measured_value": str(item.measured_value),
        "designed_value": None if item.designed_value is None else str(item.designed_value),
        "deviation_percent": None if deviation is None else str(deviation),
        "unit": item.unit,
        "system_id": item.system_id,
        "point_id": item.point_id,
        "origin": item.origin.value,
        "evidence_ref": item.evidence_ref,
    }


def _validate_references(
    systems: tuple[VentilationSystemRef, ...],
    checkpoints: tuple[OvkCheckpoint, ...],
    measurements: tuple[OvkMeasurement, ...],
    findings: tuple[OvkFinding, ...],
    actions: tuple[OvkAction, ...],
) -> None:
    system_ids = {item.system_id for item in systems}
    checkpoint_ids = {item.checkpoint_id for item in checkpoints}
    finding_ids = {item.finding_id for item in findings}

    _ensure_unique("system_id", len(system_ids), len(systems))
    _ensure_unique("checkpoint_id", len(checkpoint_ids), len(checkpoints))
    _ensure_unique("measurement_id", len({item.measurement_id for item in measurements}), len(measurements))
    _ensure_unique("finding_id", len(finding_ids), len(findings))
    _ensure_unique("action_id", len({item.action_id for item in actions}), len(actions))

    for item in checkpoints:
        _validate_system_ref(item.system_id, system_ids)
    for item in measurements:
        _validate_system_ref(item.system_id, system_ids)
    for item in findings:
        _validate_system_ref(item.system_id, system_ids)
        if item.checkpoint_id is not None and item.checkpoint_id not in checkpoint_ids:
            raise ValueError(f"unknown checkpoint_id: {item.checkpoint_id}")
    for item in actions:
        if item.finding_id not in finding_ids:
            raise ValueError(f"unknown finding_id: {item.finding_id}")


def _validate_system_ref(system_id: str | None, system_ids: set[str]) -> None:
    if system_id is not None and system_id not in system_ids:
        raise ValueError(f"unknown system_id: {system_id}")


def _ensure_unique(name: str, unique_count: int, total_count: int) -> None:
    if unique_count != total_count:
        raise ValueError(f"duplicate {name}")
