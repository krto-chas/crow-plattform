"""Uppdragsöversikt för OVK:s skrivbordsarbetsplats.

En rutt som ger organisationens uppdrag med härledd status och nästa steg.
Statusen lagras inte: den räknas fram ur besiktningsposten, fältets
ögonblicksbild, utfärdade intyg och ombesiktningsärenden, så att den aldrig kan
säga något annat än underlaget.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from crow_ovk_fastighet import BesiktningsmanRepository, Fastighet, FastighetRepository
from fastapi import APIRouter, Request

from crow_ovk import InspectionConclusion
from crow_ovk_intyg import OvkIntyg, OvkIntygRepository
from crow_ovk_workflow import (
    CaseStatus,
    OvkReinspectionCase,
    OvkReinspectionRepository,
    OvkWorkflowRecord,
    OvkWorkflowRepository,
)

from .ovk_scope import current_actor, visible_project_ids

STATUS_LABELS: dict[str, str] = {
    "ej_planerad": "Ej planerad",
    "planerad": "Planerad",
    "pagaende": "Pågående",
    "att_granska": "Att granska",
    "leveransklar": "Leveransklar",
    "utfardad": "Utfärdad",
    "atgarder_oppna": "Åtgärder öppna",
    "ombesiktning": "Ombesiktning",
}


def derive_status(
    *,
    planned: bool,
    has_snapshot: bool,
    field_completed: bool,
    protocol_ready: bool,
    issued: bool,
    deficiencies: bool,
    reinspection: CaseStatus | None,
) -> str:
    """Visningsstatus för ett uppdrag, härledd ur befintliga uppgifter.

    ``reinspection`` är status för uppdragets senaste ombesiktningsärende, eller
    ``None`` om inget finns. Levererad saknas tills leveranser registreras.
    """
    if issued:
        if reinspection in (CaseStatus.OPEN, CaseStatus.READY):
            return "ombesiktning"
        if deficiencies and reinspection is None:
            return "atgarder_oppna"
        return "utfardad"
    if protocol_ready:
        return "leveransklar"
    if field_completed:
        return "att_granska"
    if has_snapshot:
        return "pagaende"
    if planned:
        return "planerad"
    return "ej_planerad"


def ovk_overview_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    workflows = OvkWorkflowRepository(data_root)
    properties = FastighetRepository(data_root)
    inspectors = BesiktningsmanRepository(data_root)
    certificates = OvkIntygRepository(data_root)
    reinspections = OvkReinspectionRepository(data_root)

    def inspector_name(inspector_id: str, cache: dict[str, str | None]) -> str | None:
        if inspector_id not in cache:
            try:
                cache[inspector_id] = inspectors.load(inspector_id).namn
            except (OSError, ValueError, KeyError, TypeError):
                cache[inspector_id] = None
        return cache[inspector_id]

    @router.get("/api/ovk/uppdrag", response_model=None)
    def list_assignments(request: Request) -> dict[str, Any]:
        actor = current_actor(request)
        items: list[dict[str, Any]] = []
        unreadable: list[dict[str, str]] = []
        names: dict[str, str | None] = {}
        for project_id in visible_project_ids(data_root, actor):
            directory = data_root / "projects" / project_id / "ovk"
            if not directory.is_dir():
                continue
            try:
                project_properties = properties.list(project_id)
                project_certificates = certificates.list(project_id)
                project_cases = reinspections.list(project_id)
            except (OSError, ValueError, KeyError, TypeError):
                # Utan intyg eller ärenden kan status bli fel. Hellre ett
                # redovisat läsfel än en rad som påstår något osant.
                unreadable.append({"project_id": project_id, "inspection_id": ""})
                continue
            for path in sorted(directory.glob("*.json")):
                try:
                    record = workflows.load(project_id, path.stem)
                except (OSError, ValueError, KeyError, TypeError):
                    unreadable.append({"project_id": project_id, "inspection_id": path.stem})
                    continue
                field = _field_state(data_root, project_id, record.inspection.inspection_id)
                if field is None:
                    unreadable.append({"project_id": project_id, "inspection_id": path.stem})
                    continue
                items.append(
                    _assignment(
                        record,
                        field=field,
                        properties=project_properties,
                        certificates=project_certificates,
                        cases=project_cases,
                        inspector=(
                            inspector_name(record.planning.inspector_id, names)
                            if record.planning
                            else None
                        ),
                    )
                )
        counts = dict.fromkeys(STATUS_LABELS, 0)
        for item in items:
            counts[item["status"]] += 1
        return {
            "uppdrag": items,
            "antal": counts,
            "statusar": STATUS_LABELS,
            "ej_lasbara": unreadable,
            "fullstandig": not unreadable,
        }

    return router


def _field_state(data_root: Path, project_id: str, inspection_id: str) -> dict[str, Any] | None:
    """Fältets läge ur ögonblicksbilden. ``None`` om den finns men inte går att läsa."""
    path = data_root / "projects" / project_id / "ovk-field" / inspection_id / "snapshot.json"
    if not path.is_file():
        return {"synkad": False, "senast_synkad": None, "avslutat": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    completed = payload.get("field_work_completed_at")
    return {
        "synkad": True,
        "senast_synkad": modified.isoformat(timespec="seconds"),
        "avslutat": completed if isinstance(completed, str) and completed else None,
    }


def _assignment(
    record: OvkWorkflowRecord,
    *,
    field: dict[str, Any],
    properties: tuple[Fastighet, ...],
    certificates: tuple[OvkIntyg, ...],
    cases: tuple[OvkReinspectionCase, ...],
    inspector: str | None,
) -> dict[str, Any]:
    inspection = record.inspection
    obj = inspection.ovk_object
    inspection_id = inspection.inspection_id
    fastighet = next((item for item in properties if item.fastighet_id == obj.object_id), None)
    byggnad = (
        next((b for b in fastighet.byggnader if b.byggnad_id == obj.building_id), None)
        if fastighet
        else None
    )
    issued = sorted(
        (item for item in certificates if item.inspection_id == inspection_id),
        key=lambda item: (item.issued_date, item.intyg_id),
    )
    own_cases = sorted(
        (case for case in cases if case.source_inspection_id == inspection_id),
        key=lambda case: (case.opened_at, case.case_id),
    )
    status = derive_status(
        planned=record.planning is not None,
        has_snapshot=bool(field["synkad"]),
        field_completed=field["avslutat"] is not None,
        protocol_ready=record.protocol_ready,
        issued=bool(issued),
        deficiencies=inspection.conclusion is InspectionConclusion.DEFICIENCIES,
        reinspection=own_cases[-1].status if own_cases else None,
    )
    planning = record.planning
    return {
        "project_id": obj.project_id,
        "inspection_id": inspection_id,
        "objekt": obj.name,
        "fastighetsbeteckning": fastighet.fastighetsbeteckning if fastighet else None,
        "adress": _address(fastighet) if fastighet else obj.address,
        "byggnad": byggnad.internt_namn if byggnad else None,
        "system": [system.system_type for system in inspection.systems],
        "besiktningsman": inspector,
        "planerat_datum": planning.planned_date.isoformat() if planning else None,
        "uppdragstyp": planning.inspection_type if planning else None,
        "status": status,
        "status_text": STATUS_LABELS[status],
        "resultat": inspection.conclusion.value,
        "tackning_klar": record.coverage_complete,
        "oppna_granskningar": record.unresolved_review_count,
        "falt": field,
        "intyg_id": issued[-1].intyg_id if issued else None,
        "utfardat": issued[-1].issued_date.isoformat() if issued else None,
        "uppdaterad": record.updated_at or None,
        "nasta_steg": _next_step(status, obj.project_id, inspection_id),
    }


def _address(fastighet: Fastighet) -> str | None:
    adress = fastighet.byggnadens_adress
    parts = [adress.gata.strip(), " ".join(p for p in (adress.postnr, adress.ort) if p).strip()]
    text = ", ".join(part for part in parts if part)
    return text or None


def _next_step(status: str, project_id: str, inspection_id: str) -> dict[str, str]:
    query = (
        f"?project_id={quote(project_id, safe='')}&inspection_id={quote(inspection_id, safe='')}"
    )
    project_query = f"?project_id={quote(project_id, safe='')}"
    steps: dict[str, tuple[str, str]] = {
        "ej_planerad": ("Planera", "/ovk/besiktning" + query),
        "planerad": ("Öppna i fält", "/ovk/falt" + query),
        "pagaende": ("Följ fältarbetet", "/ovk/besiktning" + query),
        "att_granska": ("Granska", "/ovk/besiktning" + query),
        "leveransklar": ("Utfärda intyg", "/ovk/intyg" + project_query),
        "utfardad": ("Visa intyg", "/ovk/intyg" + project_query),
        "atgarder_oppna": ("Öppna ombesiktning", "/ovk/ombesiktning" + project_query),
        "ombesiktning": ("Följ ombesiktning", "/ovk/ombesiktning" + project_query),
    }
    text, href = steps[status]
    return {"text": text, "href": href}
