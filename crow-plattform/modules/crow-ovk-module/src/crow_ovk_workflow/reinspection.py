"""Ombesiktningsflöde: underkänd → åtgärd uppgiven → verifierad → godkänd.

Åtgärder som byggnadsägaren uppger är STATED och kräver skriven notering.
Verifiering sker av funktionskontrollanten vid ombesiktningen, är OBSERVED
och kräver ombesiktningens besiktnings-ID. Ärendet kan bara stängas mot ett
protokollklart, godkänt ombesiktningsrecord där samtliga punkter verifierats.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from crow_ovk import EvidenceOrigin, FindingSeverity, InspectionConclusion

from .models import OvkWorkflowRecord

REINSPECTION_SCHEMA_VERSION = "crow-ovk-ombesiktning-v0.1"

_ALLOWED_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


class RemedyState(StrEnum):
    OPEN = "open"
    REMEDY_CLAIMED = "remedy_claimed"
    VERIFIED = "verified"
    FAILED = "failed"


class CaseStatus(StrEnum):
    OPEN = "open"
    READY = "ready"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class ReinspectionItem:
    finding_id: str
    description: str
    severity: FindingSeverity
    system_id: str | None = None
    state: RemedyState = RemedyState.OPEN
    remedy_note: str = ""
    remedy_evidence_ref: str | None = None
    remedy_origin: EvidenceOrigin = EvidenceOrigin.STATED
    verified_in: str | None = None
    verification_note: str = ""

    def __post_init__(self) -> None:
        if self.state is RemedyState.REMEDY_CLAIMED and not self.remedy_note.strip():
            raise ValueError("remedy claim requires a written note")
        if self.state in (RemedyState.VERIFIED, RemedyState.FAILED) and not self.verified_in:
            raise ValueError("verification requires the reinspection id")


@dataclass(frozen=True, slots=True)
class OvkReinspectionCase:
    case_id: str
    project_id: str
    building_id: str
    source_inspection_id: str
    items: tuple[ReinspectionItem, ...]
    opened_at: str
    deadline: date | None = None
    result_inspection_id: str | None = None
    closed_at: str | None = None

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("reinspection case requires at least one item")
        if (self.result_inspection_id is None) != (self.closed_at is None):
            raise ValueError("closed case requires both result_inspection_id and closed_at")

    @property
    def all_verified(self) -> bool:
        return all(item.state is RemedyState.VERIFIED for item in self.items)

    @property
    def status(self) -> CaseStatus:
        if self.closed_at is not None:
            return CaseStatus.CLOSED
        if self.all_verified:
            return CaseStatus.READY
        return CaseStatus.OPEN


def open_case(
    record: OvkWorkflowRecord,
    *,
    case_id: str,
    opened_at: str | None = None,
    deadline: date | None = None,
) -> OvkReinspectionCase:
    if not record.protocol_ready:
        raise ValueError("OVK workflow is not protocol ready; case cannot be opened")
    if record.inspection.conclusion is not InspectionConclusion.DEFICIENCIES:
        raise ValueError("reinspection case requires a deficiencies conclusion")
    items = tuple(
        ReinspectionItem(
            finding_id=finding.finding_id,
            description=finding.description,
            severity=finding.severity,
            system_id=finding.system_id,
        )
        for finding in record.inspection.findings
        if finding.action_required
    )
    if not items:
        raise ValueError("no findings with action_required to remedy")
    return OvkReinspectionCase(
        case_id=case_id,
        project_id=record.inspection.ovk_object.project_id,
        building_id=record.inspection.ovk_object.building_id,
        source_inspection_id=record.inspection.inspection_id,
        items=items,
        opened_at=opened_at or datetime.now(UTC).isoformat(),
        deadline=deadline,
    )


def claim_remedy(
    case: OvkReinspectionCase,
    finding_id: str,
    *,
    note: str,
    evidence_ref: str | None = None,
) -> OvkReinspectionCase:
    _require_open(case)
    item = _item(case, finding_id)
    if item.state is RemedyState.VERIFIED:
        raise ValueError(f"finding {finding_id!r} is already verified")
    updated = replace(
        item,
        state=RemedyState.REMEDY_CLAIMED,
        remedy_note=note,
        remedy_evidence_ref=evidence_ref,
        remedy_origin=EvidenceOrigin.STATED,
        verified_in=None,
        verification_note="",
    )
    return _with_item(case, updated)


def verify_item(
    case: OvkReinspectionCase,
    finding_id: str,
    *,
    verified: bool,
    reinspection_id: str,
    note: str = "",
) -> OvkReinspectionCase:
    _require_open(case)
    if not reinspection_id.strip():
        raise ValueError("reinspection_id is required for verification")
    item = _item(case, finding_id)
    updated = replace(
        item,
        state=RemedyState.VERIFIED if verified else RemedyState.FAILED,
        verified_in=reinspection_id,
        verification_note=note,
    )
    return _with_item(case, updated)


def close_case(
    case: OvkReinspectionCase,
    *,
    reinspection_record: OvkWorkflowRecord,
    closed_at: str | None = None,
) -> OvkReinspectionCase:
    _require_open(case)
    if not reinspection_record.protocol_ready:
        raise ValueError("reinspection workflow is not protocol ready")
    if reinspection_record.inspection.conclusion is not InspectionConclusion.APPROVED:
        raise ValueError("reinspection workflow is not approved")
    reinspection_id = reinspection_record.inspection.inspection_id
    if reinspection_id == case.source_inspection_id:
        raise ValueError("reinspection record cannot be the source inspection")
    unverified = sorted(
        item.finding_id for item in case.items if item.state is not RemedyState.VERIFIED
    )
    if unverified:
        raise ValueError("unverified findings remain: " + ", ".join(unverified))
    mismatched = sorted(
        item.finding_id for item in case.items if item.verified_in != reinspection_id
    )
    if mismatched:
        raise ValueError("findings verified against another reinspection: " + ", ".join(mismatched))
    return replace(
        case,
        result_inspection_id=reinspection_id,
        closed_at=closed_at or datetime.now(UTC).isoformat(),
    )


def case_to_payload(case: OvkReinspectionCase) -> dict[str, Any]:
    return {
        "schema_version": REINSPECTION_SCHEMA_VERSION,
        "case_id": case.case_id,
        "project_id": case.project_id,
        "building_id": case.building_id,
        "source_inspection_id": case.source_inspection_id,
        "opened_at": case.opened_at,
        "deadline": case.deadline.isoformat() if case.deadline is not None else None,
        "result_inspection_id": case.result_inspection_id,
        "closed_at": case.closed_at,
        "status": case.status.value,
        "items": [
            {
                "finding_id": item.finding_id,
                "description": item.description,
                "severity": item.severity.value,
                "system_id": item.system_id,
                "state": item.state.value,
                "remedy_note": item.remedy_note,
                "remedy_evidence_ref": item.remedy_evidence_ref,
                "remedy_origin": item.remedy_origin.value,
                "verified_in": item.verified_in,
                "verification_note": item.verification_note,
            }
            for item in case.items
        ],
    }


def case_from_payload(payload: dict[str, Any]) -> OvkReinspectionCase:
    return OvkReinspectionCase(
        case_id=_required_text(payload, "case_id"),
        project_id=_required_text(payload, "project_id"),
        building_id=_required_text(payload, "building_id"),
        source_inspection_id=_required_text(payload, "source_inspection_id"),
        items=tuple(_item_from_payload(item) for item in _list(payload.get("items"), "items")),
        opened_at=_required_text(payload, "opened_at"),
        deadline=_optional_date(payload.get("deadline")),
        result_inspection_id=_optional_text(payload.get("result_inspection_id")),
        closed_at=_optional_text(payload.get("closed_at")),
    )


class OvkReinspectionRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, case: OvkReinspectionCase) -> Path:
        path = self._path(case.project_id, case.case_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(case_to_payload(case), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)
        return path

    def load(self, project_id: str, case_id: str) -> OvkReinspectionCase:
        path = self._path(project_id, case_id)
        if not path.exists():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("stored reinspection case must be an object")
        return case_from_payload(payload)

    def list(self, project_id: str) -> tuple[OvkReinspectionCase, ...]:
        _safe_identifier(project_id, "project_id")
        directory = self.root / "projects" / project_id / "ovk-ombesiktning"
        if not directory.exists():
            return ()
        return tuple(self.load(project_id, path.stem) for path in sorted(directory.glob("*.json")))

    def _path(self, project_id: str, case_id: str) -> Path:
        _safe_identifier(project_id, "project_id")
        _safe_identifier(case_id, "case_id")
        return self.root / "projects" / project_id / "ovk-ombesiktning" / f"{case_id}.json"


def _require_open(case: OvkReinspectionCase) -> None:
    if case.closed_at is not None:
        raise ValueError(f"case {case.case_id!r} is closed")


def _item(case: OvkReinspectionCase, finding_id: str) -> ReinspectionItem:
    for item in case.items:
        if item.finding_id == finding_id:
            return item
    raise ValueError(f"finding {finding_id!r} is not part of case {case.case_id!r}")


def _with_item(case: OvkReinspectionCase, updated: ReinspectionItem) -> OvkReinspectionCase:
    items = tuple(updated if item.finding_id == updated.finding_id else item for item in case.items)
    return replace(case, items=items)


def _item_from_payload(value: object) -> ReinspectionItem:
    item = _mapping(value, "item")
    return ReinspectionItem(
        finding_id=_required_text(item, "finding_id"),
        description=_required_text(item, "description"),
        severity=FindingSeverity(_required_text(item, "severity")),
        system_id=_optional_text(item.get("system_id")),
        state=RemedyState(str(item.get("state", RemedyState.OPEN.value))),
        remedy_note=str(item.get("remedy_note", "")),
        remedy_evidence_ref=_optional_text(item.get("remedy_evidence_ref")),
        remedy_origin=EvidenceOrigin(str(item.get("remedy_origin", EvidenceOrigin.STATED.value))),
        verified_in=_optional_text(item.get("verified_in")),
        verification_note=str(item.get("verification_note", "")),
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


def _optional_date(value: object) -> date | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid date {text!r}") from exc


def _safe_identifier(value: str, field: str) -> None:
    if not value or any(char not in _ALLOWED_ID_CHARS for char in value):
        raise ValueError(f"invalid {field}")
