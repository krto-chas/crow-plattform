"""Bygger OVK-intyg ur protokollklara workflowrecords med härledd nästa frist."""

from __future__ import annotations

from datetime import date
from typing import Any

from crow_ovk import EvidenceOrigin, InspectionConclusion
from crow_ovk_pricing import BuildingCategory, InspectionType, OvkTaxa, VentilationSystemType
from crow_ovk_pricing import load_taxa as load_ovk_taxa
from crow_ovk_workflow import OvkWorkflowRecord

from .models import (
    SCHEMA_VERSION,
    Behorighet,
    Byggnadsagare,
    Funktionskontrollant,
    IntygResult,
    IntygSystemRow,
    NextInspection,
    OvkIntyg,
)


def build_intyg(
    *,
    intyg_id: str,
    record: OvkWorkflowRecord,
    fastighetsbeteckning: str,
    byggnadsagare: Byggnadsagare,
    funktionskontrollant: Funktionskontrollant,
    inspection_type: InspectionType,
    inspection_date: date,
    building_category: BuildingCategory,
    school_or_care: bool = False,
    issued_date: date | None = None,
    taxa: OvkTaxa | None = None,
) -> OvkIntyg:
    if not record.protocol_ready:
        raise ValueError("OVK workflow is not protocol ready; intyg cannot be issued")
    conclusion = record.inspection.conclusion
    if conclusion is InspectionConclusion.PENDING:
        raise ValueError("OVK inspection conclusion is pending; intyg cannot be issued")

    result = (
        IntygResult.GODKAND
        if conclusion is InspectionConclusion.APPROVED
        else IntygResult.EJ_GODKAND
    )
    failing_systems = {
        finding.system_id
        for finding in record.inspection.findings
        if finding.action_required and finding.system_id is not None
    }
    systems = tuple(
        IntygSystemRow(
            system_id=system.system_id,
            system_type=system.system_type,
            label=system.label,
            result=(
                IntygResult.EJ_GODKAND
                if system.system_id in failing_systems
                else IntygResult.GODKAND
            ),
        )
        for system in record.inspection.systems
    )
    next_inspection = _derive_next_inspection(
        result=result,
        inspection_date=inspection_date,
        building_category=building_category,
        school_or_care=school_or_care,
        systems=systems,
        taxa=taxa or load_ovk_taxa(),
    )
    return OvkIntyg(
        intyg_id=intyg_id,
        inspection_id=record.inspection.inspection_id,
        project_id=record.inspection.ovk_object.project_id,
        building_id=record.inspection.ovk_object.building_id,
        object_name=record.inspection.ovk_object.name,
        fastighetsbeteckning=fastighetsbeteckning,
        byggnadsagare=byggnadsagare,
        funktionskontrollant=funktionskontrollant,
        inspection_type=inspection_type,
        inspection_date=inspection_date,
        issued_date=issued_date or inspection_date,
        systems=systems,
        result=result,
        next_inspection=next_inspection,
        address=record.inspection.ovk_object.address,
    )


def _derive_next_inspection(
    *,
    result: IntygResult,
    inspection_date: date,
    building_category: BuildingCategory,
    school_or_care: bool,
    systems: tuple[IntygSystemRow, ...],
    taxa: OvkTaxa,
) -> NextInspection:
    if result is IntygResult.EJ_GODKAND:
        return NextInspection(
            interval_years=None,
            due_date=None,
            origin=EvidenceOrigin.INFERRED,
            basis=(
                "Ingen ny frist härledd: besiktningen är ej godkänd och "
                "ombesiktning krävs efter åtgärdade brister."
            ),
        )
    intervals: list[int] = []
    for system in systems:
        interval = taxa.recurring_interval_years(
            building_category,
            _system_type(system.system_type),
            school_or_care=school_or_care,
        )
        if interval is not None:
            intervals.append(interval)
    if not intervals:
        return NextInspection(
            interval_years=None,
            due_date=None,
            origin=EvidenceOrigin.INFERRED,
            basis=(
                "Ingen återkommande frist härledd: byggnadskategorin "
                f"{building_category.value!r} saknar återkommande OVK-krav "
                "enligt BFS 2011:16 för de registrerade systemtyperna."
            ),
        )
    years = min(intervals)
    due_date = _add_years(inspection_date, years)
    system_types = ", ".join(sorted({system.system_type for system in systems}))
    return NextInspection(
        interval_years=years,
        due_date=due_date,
        origin=EvidenceOrigin.INFERRED,
        basis=(
            f"Härledd: besiktningsdatum {inspection_date.isoformat()} + {years} år, "
            "kortaste återkommande intervall enligt BFS 2011:16 för "
            f"{building_category.value} med systemtyp {system_types}."
        ),
    )


def _system_type(value: str) -> VentilationSystemType | None:
    try:
        return VentilationSystemType(value.strip().upper())
    except ValueError:
        return None


def _add_years(anchor: date, years: int) -> date:
    try:
        return anchor.replace(year=anchor.year + years)
    except ValueError:
        return anchor.replace(year=anchor.year + years, day=28)


def intyg_to_payload(intyg: OvkIntyg) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "intyg_id": intyg.intyg_id,
        "inspection_id": intyg.inspection_id,
        "project_id": intyg.project_id,
        "building_id": intyg.building_id,
        "object_name": intyg.object_name,
        "fastighetsbeteckning": intyg.fastighetsbeteckning,
        "address": intyg.address,
        "byggnadsagare": {
            "name": intyg.byggnadsagare.name,
            "contact": intyg.byggnadsagare.contact,
        },
        "funktionskontrollant": {
            "name": intyg.funktionskontrollant.name,
            "behorighet": intyg.funktionskontrollant.behorighet.value,
            "certification_body": intyg.funktionskontrollant.certification_body,
            "certificate_number": intyg.funktionskontrollant.certificate_number,
            "certificate_valid_to": (
                intyg.funktionskontrollant.certificate_valid_to.isoformat()
                if intyg.funktionskontrollant.certificate_valid_to is not None
                else None
            ),
        },
        "inspection_type": intyg.inspection_type.value,
        "inspection_date": intyg.inspection_date.isoformat(),
        "issued_date": intyg.issued_date.isoformat(),
        "systems": [
            {
                "system_id": system.system_id,
                "system_type": system.system_type,
                "label": system.label,
                "result": system.result.value,
            }
            for system in intyg.systems
        ],
        "result": intyg.result.value,
        "next_inspection": {
            "interval_years": intyg.next_inspection.interval_years,
            "due_date": (
                intyg.next_inspection.due_date.isoformat()
                if intyg.next_inspection.due_date is not None
                else None
            ),
            "origin": intyg.next_inspection.origin.value,
            "basis": intyg.next_inspection.basis,
        },
    }


def intyg_from_payload(payload: dict[str, Any]) -> OvkIntyg:
    owner = _mapping(payload.get("byggnadsagare"), "byggnadsagare")
    kontrollant = _mapping(payload.get("funktionskontrollant"), "funktionskontrollant")
    next_payload = _mapping(payload.get("next_inspection"), "next_inspection")
    interval_value = next_payload.get("interval_years")
    return OvkIntyg(
        intyg_id=_required_text(payload, "intyg_id"),
        inspection_id=_required_text(payload, "inspection_id"),
        project_id=_required_text(payload, "project_id"),
        building_id=_required_text(payload, "building_id"),
        object_name=_required_text(payload, "object_name"),
        fastighetsbeteckning=_required_text(payload, "fastighetsbeteckning"),
        byggnadsagare=Byggnadsagare(
            name=_required_text(owner, "name"),
            contact=_optional_text(owner.get("contact")),
        ),
        funktionskontrollant=Funktionskontrollant(
            name=_required_text(kontrollant, "name"),
            behorighet=Behorighet(_required_text(kontrollant, "behorighet")),
            certification_body=_required_text(kontrollant, "certification_body"),
            certificate_number=_required_text(kontrollant, "certificate_number"),
            certificate_valid_to=_optional_date(kontrollant.get("certificate_valid_to")),
        ),
        inspection_type=InspectionType(_required_text(payload, "inspection_type")),
        inspection_date=_required_date(payload, "inspection_date"),
        issued_date=_required_date(payload, "issued_date"),
        systems=tuple(_system_row(item) for item in _list(payload.get("systems"), "systems")),
        result=IntygResult(_required_text(payload, "result")),
        next_inspection=NextInspection(
            interval_years=int(interval_value) if interval_value is not None else None,
            due_date=_optional_date(next_payload.get("due_date")),
            origin=EvidenceOrigin(_required_text(next_payload, "origin")),
            basis=_required_text(next_payload, "basis"),
        ),
        address=_optional_text(payload.get("address")),
    )


def _system_row(value: object) -> IntygSystemRow:
    item = _mapping(value, "system")
    return IntygSystemRow(
        system_id=_required_text(item, "system_id"),
        system_type=_required_text(item, "system_type"),
        label=_required_text(item, "label"),
        result=IntygResult(_required_text(item, "result")),
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


def _required_date(item: dict[str, Any], key: str) -> date:
    parsed = _optional_date(item.get(key))
    if parsed is None:
        raise ValueError(f"{key} is required")
    return parsed


def _optional_date(value: object) -> date | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid date {text!r}") from exc
