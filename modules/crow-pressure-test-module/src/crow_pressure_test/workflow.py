from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from .knowledge import PressureTestKnowledge
from .models import ClaimOrigin, TightnessClass

SCHEMA_VERSION = "crow-pressure-test-workflow-v0.1"


class PressureTestStatus(StrEnum):
    NOT_MEASURED = "not_measured"
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class RequirementProvenance:
    field: str
    value: str
    origin: ClaimOrigin
    source_ref: str | None = None
    confirmed: bool = False

    @property
    def requires_confirmation(self) -> bool:
        return self.origin is ClaimOrigin.INFERRED and not self.confirmed


@dataclass(frozen=True, slots=True)
class PressureTestEvaluation:
    project_id: str
    tightness_class: TightnessClass
    pressure_pa: int
    duct_area_m2: Decimal
    allowed_leakage_lps: Decimal
    measured_leakage_lps: Decimal | None
    status: PressureTestStatus
    ready_for_protocol: bool
    provenance: tuple[RequirementProvenance, ...]
    atc_class: str
    standards: tuple[tuple[str, str], ...]


def evaluate_pressure_test(
    *,
    project_id: str,
    tightness_class: TightnessClass,
    pressure_pa: int,
    duct_area_m2: Decimal,
    measured_leakage_lps: Decimal | None,
    provenance: tuple[RequirementProvenance, ...],
    knowledge: PressureTestKnowledge,
) -> PressureTestEvaluation:
    if measured_leakage_lps is not None and measured_leakage_lps < 0:
        raise ValueError("measured_leakage_lps must be non-negative")

    allowed = knowledge.allowed_leakage_flow(tightness_class, pressure_pa, duct_area_m2)
    if measured_leakage_lps is None:
        status = PressureTestStatus.NOT_MEASURED
    elif measured_leakage_lps <= allowed:
        status = PressureTestStatus.PASS
    else:
        status = PressureTestStatus.FAIL

    blocked_by_inference = any(item.requires_confirmation for item in provenance)
    ready_for_protocol = measured_leakage_lps is not None and not blocked_by_inference
    standards = tuple((item.standard_id, item.title) for item in knowledge.standards())

    return PressureTestEvaluation(
        project_id=project_id,
        tightness_class=tightness_class,
        pressure_pa=pressure_pa,
        duct_area_m2=duct_area_m2,
        allowed_leakage_lps=allowed,
        measured_leakage_lps=measured_leakage_lps,
        status=status,
        ready_for_protocol=ready_for_protocol,
        provenance=provenance,
        atc_class=knowledge.atc_class(tightness_class),
        standards=standards,
    )


def evaluation_to_payload(result: PressureTestEvaluation) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": result.project_id,
        "tightness_class": result.tightness_class.value,
        "pressure_pa": str(result.pressure_pa),
        "duct_area_m2": str(result.duct_area_m2),
        "allowed_leakage_lps": str(result.allowed_leakage_lps),
        "measured_leakage_lps": (
            None if result.measured_leakage_lps is None else str(result.measured_leakage_lps)
        ),
        "status": result.status.value,
        "ready_for_protocol": result.ready_for_protocol,
        "atc_class": result.atc_class,
        "standards": [
            {"id": standard_id, "title": title} for standard_id, title in result.standards
        ],
        "provenance": [
            {
                "field": item.field,
                "value": item.value,
                "origin": item.origin.value,
                "source_ref": item.source_ref,
                "confirmed": item.confirmed,
                "requires_confirmation": item.requires_confirmation,
            }
            for item in result.provenance
        ],
    }
