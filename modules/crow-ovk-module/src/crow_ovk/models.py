from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class EvidenceOrigin(StrEnum):
    STATED = "stated"
    MEASURED = "measured"
    OBSERVED = "observed"
    INFERRED = "inferred"


class CheckStatus(StrEnum):
    NOT_CHECKED = "not_checked"
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class FindingSeverity(StrEnum):
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"


class ActionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class InspectionConclusion(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DEFICIENCIES = "deficiencies"


@dataclass(frozen=True, slots=True)
class OvkObject:
    object_id: str
    project_id: str
    building_id: str
    name: str
    address: str | None = None


@dataclass(frozen=True, slots=True)
class VentilationSystemRef:
    system_id: str
    system_type: str
    label: str
    source_ref: str | None = None


@dataclass(frozen=True, slots=True)
class OvkCheckpoint:
    checkpoint_id: str
    label: str
    status: CheckStatus
    system_id: str | None = None
    note: str = ""
    origin: EvidenceOrigin = EvidenceOrigin.OBSERVED
    evidence_ref: str | None = None


@dataclass(frozen=True, slots=True)
class OvkMeasurement:
    measurement_id: str
    metric: str
    measured_value: Decimal
    unit: str
    system_id: str | None = None
    point_id: str | None = None
    designed_value: Decimal | None = None
    origin: EvidenceOrigin = EvidenceOrigin.MEASURED
    evidence_ref: str | None = None

    @property
    def deviation_percent(self) -> Decimal | None:
        if self.designed_value is None or self.designed_value == 0:
            return None
        return (
            (self.measured_value - self.designed_value)
            / self.designed_value
            * Decimal("100")
        )


@dataclass(frozen=True, slots=True)
class OvkFinding:
    finding_id: str
    description: str
    severity: FindingSeverity
    checkpoint_id: str | None = None
    system_id: str | None = None
    action_required: bool = True
    origin: EvidenceOrigin = EvidenceOrigin.OBSERVED
    evidence_ref: str | None = None


@dataclass(frozen=True, slots=True)
class OvkAction:
    action_id: str
    finding_id: str
    description: str
    status: ActionStatus = ActionStatus.OPEN


@dataclass(frozen=True, slots=True)
class OvkInspection:
    inspection_id: str
    ovk_object: OvkObject
    systems: tuple[VentilationSystemRef, ...]
    checkpoints: tuple[OvkCheckpoint, ...]
    measurements: tuple[OvkMeasurement, ...]
    findings: tuple[OvkFinding, ...]
    actions: tuple[OvkAction, ...]
    conclusion: InspectionConclusion
