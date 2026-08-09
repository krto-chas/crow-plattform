from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from crow_ovk import (
    ActionStatus,
    CheckStatus,
    EvidenceOrigin,
    FindingSeverity,
    OvkAction,
    OvkCheckpoint,
    OvkFinding,
    OvkMeasurement,
    OvkObject,
    VentilationSystemRef,
    build_inspection,
    inspection_to_payload,
)

from .models import OvkReviewDecision, OvkWorkflowRecord, ReviewStatus

SCHEMA_VERSION = "crow-ovk-workflow-v0.1"


def build_record(
    *,
    inspection_id: str,
    ovk_object: OvkObject,
    systems: tuple[VentilationSystemRef, ...] = (),
    checkpoints: tuple[OvkCheckpoint, ...] = (),
    measurements: tuple[OvkMeasurement, ...] = (),
    findings: tuple[OvkFinding, ...] = (),
    actions: tuple[OvkAction, ...] = (),
    review: tuple[OvkReviewDecision, ...] = (),
    updated_at: str | None = None,
) -> OvkWorkflowRecord:
    inspection = build_inspection(
        inspection_id=inspection_id,
        ovk_object=ovk_object,
        systems=systems,
        checkpoints=checkpoints,
        measurements=measurements,
        findings=findings,
        actions=actions,
    )
    if not checkpoints:
        from crow_ovk.models import InspectionConclusion, OvkInspection

        inspection = OvkInspection(
            inspection_id=inspection.inspection_id,
            ovk_object=inspection.ovk_object,
            systems=inspection.systems,
            checkpoints=inspection.checkpoints,
            measurements=inspection.measurements,
            findings=inspection.findings,
            actions=inspection.actions,
            conclusion=InspectionConclusion.PENDING,
        )
    return OvkWorkflowRecord(
        inspection=inspection,
        review=review,
        updated_at=updated_at or datetime.now(UTC).isoformat(),
    )


def record_to_payload(record: OvkWorkflowRecord) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "inspection": inspection_to_payload(record.inspection),
        "review": [
            {
                "observation_id": item.observation_id,
                "source_text": item.source_text,
                "evidence_ref": item.evidence_ref,
                "reason": item.reason,
                "status": item.status.value,
                "reviewer": item.reviewer,
                "note": item.note,
            }
            for item in record.review
        ],
        "unresolved_review_count": record.unresolved_review_count,
        "protocol_ready": record.protocol_ready,
        "updated_at": record.updated_at,
    }


def record_from_payload(payload: dict[str, Any]) -> OvkWorkflowRecord:
    inspection = _mapping(payload.get("inspection"), "inspection")
    object_payload = _mapping(inspection.get("object"), "inspection.object")
    ovk_object = OvkObject(
        object_id=_required_text(object_payload, "object_id"),
        project_id=_required_text(object_payload, "project_id"),
        building_id=_required_text(object_payload, "building_id"),
        name=_required_text(object_payload, "name"),
        address=_optional_text(object_payload.get("address")),
    )
    systems = tuple(_system(item) for item in _list(inspection.get("systems"), "systems"))
    checkpoints = tuple(
        _checkpoint(item) for item in _list(inspection.get("checkpoints"), "checkpoints")
    )
    measurements = tuple(
        _measurement(item) for item in _list(inspection.get("measurements"), "measurements")
    )
    findings = tuple(_finding(item) for item in _list(inspection.get("findings"), "findings"))
    actions = tuple(_action(item) for item in _list(inspection.get("actions"), "actions"))
    review = tuple(_review(item) for item in _list(payload.get("review"), "review"))
    return build_record(
        inspection_id=_required_text(inspection, "inspection_id"),
        ovk_object=ovk_object,
        systems=systems,
        checkpoints=checkpoints,
        measurements=measurements,
        findings=findings,
        actions=actions,
        review=review,
        updated_at=_optional_text(payload.get("updated_at")),
    )


def _system(value: object) -> VentilationSystemRef:
    item = _mapping(value, "system")
    return VentilationSystemRef(
        system_id=_required_text(item, "system_id"),
        system_type=_required_text(item, "system_type"),
        label=_required_text(item, "label"),
        source_ref=_optional_text(item.get("source_ref")),
    )


def _checkpoint(value: object) -> OvkCheckpoint:
    item = _mapping(value, "checkpoint")
    return OvkCheckpoint(
        checkpoint_id=_required_text(item, "checkpoint_id"),
        label=_required_text(item, "label"),
        status=CheckStatus(_required_text(item, "status")),
        system_id=_optional_text(item.get("system_id")),
        note=str(item.get("note", "")),
        origin=EvidenceOrigin(str(item.get("origin", EvidenceOrigin.OBSERVED.value))),
        evidence_ref=_optional_text(item.get("evidence_ref")),
    )


def _measurement(value: object) -> OvkMeasurement:
    item = _mapping(value, "measurement")
    return OvkMeasurement(
        measurement_id=_required_text(item, "measurement_id"),
        metric=_required_text(item, "metric"),
        measured_value=_decimal(item.get("measured_value"), "measured_value"),
        designed_value=_optional_decimal(item.get("designed_value"), "designed_value"),
        unit=_required_text(item, "unit"),
        system_id=_optional_text(item.get("system_id")),
        point_id=_optional_text(item.get("point_id")),
        origin=EvidenceOrigin(str(item.get("origin", EvidenceOrigin.MEASURED.value))),
        evidence_ref=_optional_text(item.get("evidence_ref")),
    )


def _finding(value: object) -> OvkFinding:
    item = _mapping(value, "finding")
    return OvkFinding(
        finding_id=_required_text(item, "finding_id"),
        description=_required_text(item, "description"),
        severity=FindingSeverity(_required_text(item, "severity")),
        checkpoint_id=_optional_text(item.get("checkpoint_id")),
        system_id=_optional_text(item.get("system_id")),
        action_required=bool(item.get("action_required", True)),
        origin=EvidenceOrigin(str(item.get("origin", EvidenceOrigin.OBSERVED.value))),
        evidence_ref=_optional_text(item.get("evidence_ref")),
    )


def _action(value: object) -> OvkAction:
    item = _mapping(value, "action")
    return OvkAction(
        action_id=_required_text(item, "action_id"),
        finding_id=_required_text(item, "finding_id"),
        description=_required_text(item, "description"),
        status=ActionStatus(str(item.get("status", ActionStatus.OPEN.value))),
    )


def _review(value: object) -> OvkReviewDecision:
    item = _mapping(value, "review")
    return OvkReviewDecision(
        observation_id=_required_text(item, "observation_id"),
        source_text=_required_text(item, "source_text"),
        evidence_ref=_required_text(item, "evidence_ref"),
        reason=_required_text(item, "reason"),
        status=ReviewStatus(str(item.get("status", ReviewStatus.PENDING.value))),
        reviewer=_optional_text(item.get("reviewer")),
        note=str(item.get("note", "")),
    )


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def _required_text(item: dict[str, Any], key: str) -> str:
    value = _optional_text(item.get(key))
    if value is None:
        raise ValueError(f"{key} is required")
    return value


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be decimal") from exc


def _optional_decimal(value: object, field: str) -> Decimal | None:
    if value in (None, ""):
        return None
    return _decimal(value, field)
