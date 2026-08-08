from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from crow_observation_engine.models import Observation, ObservationCollection
from crow_ovk import (
    EvidenceOrigin,
    FindingSeverity,
    OvkFinding,
    OvkMeasurement,
    VentilationSystemRef,
)

from .models import OvkImportResult, UnmappedObservation

_SYSTEM_RE = re.compile(r"\b(?:TA|FA|TF|FF|FTX|FT|FX)\s*[-_]?\s*\d{1,3}\b", re.IGNORECASE)
_MEASURED_RE = re.compile(
    r"(?:uppmätt|matvärde|mätvärde)\s*[:=]?\s*(-?\d+(?:[.,]\d+)?)\s*(l/s|m3/s|m³/s)",
    re.IGNORECASE,
)
_DESIGNED_RE = re.compile(
    r"(?:projekterat|börvärde|dimensionerande)\s*[:=]?\s*(-?\d+(?:[.,]\d+)?)\s*(l/s|m3/s|m³/s)",
    re.IGNORECASE,
)
_POINT_RE = re.compile(r"\b([BCLKD]\d{1,3})\b", re.IGNORECASE)
_FINDING_RE = re.compile(r"\b(anmärkning|brist)\b\s*[:\-]?\s*(.+)", re.IGNORECASE)


def import_observations(collection: ObservationCollection) -> OvkImportResult:
    systems: dict[str, VentilationSystemRef] = {}
    measurements: list[OvkMeasurement] = []
    findings: list[OvkFinding] = []
    unmapped: list[UnmappedObservation] = []

    for observation in collection.observations:
        text = observation.evidence.source_text.strip()
        evidence_ref = observation.evidence.locator.value
        matched = False

        for system_id in _system_ids(text):
            matched = True
            systems.setdefault(
                system_id,
                VentilationSystemRef(
                    system_id=system_id,
                    system_type="unknown",
                    label=system_id,
                    source_ref=evidence_ref,
                ),
            )

        measurement = _measurement_from(observation, evidence_ref)
        if measurement is not None:
            matched = True
            measurements.append(measurement)

        finding = _finding_from(observation, evidence_ref)
        if finding is not None:
            matched = True
            findings.append(finding)

        if not matched:
            unmapped.append(
                UnmappedObservation(
                    observation_id=observation.id,
                    source_text=text,
                    evidence_ref=evidence_ref,
                    reason="no_explicit_ovk_pattern",
                )
            )

    return OvkImportResult(
        project_id=collection.project_id,
        systems=tuple(systems.values()),
        measurements=tuple(measurements),
        findings=tuple(findings),
        unmapped=tuple(unmapped),
    )


def _system_ids(text: str) -> tuple[str, ...]:
    normalized = {
        re.sub(r"[\s_-]+", "", match.group(0)).upper() for match in _SYSTEM_RE.finditer(text)
    }
    return tuple(sorted(normalized))


def _measurement_from(observation: Observation, evidence_ref: str) -> OvkMeasurement | None:
    text = observation.evidence.source_text
    measured = _MEASURED_RE.search(text)
    if measured is None:
        return None

    measured_value = _decimal(measured.group(1))
    if measured_value is None:
        return None
    unit = _normalize_unit(measured.group(2))

    designed_value: Decimal | None = None
    designed = _DESIGNED_RE.search(text)
    if designed is not None and _normalize_unit(designed.group(2)) == unit:
        designed_value = _decimal(designed.group(1))

    system_ids = _system_ids(text)
    point_match = _POINT_RE.search(text)
    return OvkMeasurement(
        measurement_id=f"import:{observation.id}",
        metric="airflow",
        measured_value=measured_value,
        designed_value=designed_value,
        unit=unit,
        system_id=system_ids[0] if len(system_ids) == 1 else None,
        point_id=point_match.group(1).upper() if point_match is not None else None,
        origin=EvidenceOrigin.STATED,
        evidence_ref=evidence_ref,
    )


def _finding_from(observation: Observation, evidence_ref: str) -> OvkFinding | None:
    text = observation.evidence.source_text.strip()
    match = _FINDING_RE.search(text)
    if match is None:
        return None
    description = match.group(2).strip()
    if not description:
        return None
    system_ids = _system_ids(text)
    return OvkFinding(
        finding_id=f"import:{observation.id}",
        description=description,
        severity=FindingSeverity.INFO,
        system_id=system_ids[0] if len(system_ids) == 1 else None,
        action_required=False,
        origin=EvidenceOrigin.STATED,
        evidence_ref=evidence_ref,
    )


def _decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None


def _normalize_unit(value: str) -> str:
    normalized = value.lower()
    return "m3/s" if normalized in {"m3/s", "m³/s"} else "l/s"
