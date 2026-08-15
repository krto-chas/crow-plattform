from __future__ import annotations

from dataclasses import dataclass

from crow_ovk import OvkFinding, OvkMeasurement, VentilationSystemRef


@dataclass(frozen=True, slots=True)
class UnmappedObservation:
    observation_id: str
    source_text: str
    evidence_ref: str
    reason: str


@dataclass(frozen=True, slots=True)
class OvkImportResult:
    project_id: str
    systems: tuple[VentilationSystemRef, ...] = ()
    measurements: tuple[OvkMeasurement, ...] = ()
    findings: tuple[OvkFinding, ...] = ()
    unmapped: tuple[UnmappedObservation, ...] = ()
