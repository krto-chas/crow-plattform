"""Uppdragsöversikt för OVK:s skrivbordsarbetsplats.

En rutt som ger organisationens uppdrag med härledd status och nästa steg.
Statusen lagras inte: den räknas fram ur besiktningsposten, fältets
ögonblicksbild, protokollkällan, utfärdandemanifestet, intygens ställning och
ombesiktningsärenden. Där underlaget inte går att läsa eller inte hänger ihop
redovisas uppdraget som oläsbart i stället för att få en status.

Känd gräns: varje anrop läser alla uppdrag i alla synliga projekt. Det räcker
för en organisation i pilotskala; filter och sidindelning införs när mängden
kräver det.
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

from .ovk_certificate_status import intyg_standing
from .ovk_issuance_manifest import manifest_path
from .ovk_protocol_source import protocol_source_is_current
from .ovk_scope import current_actor, visible_project_ids

STATUS_LABELS: dict[str, str] = {
    "ej_planerad": "Ej planerad",
    "planerad": "Planerad",
    "pagaende": "Pågående",
    "att_granska": "Att granska",
    "leveransklar": "Leveransklar",
    "utfardande_avbrutet": "Utfärdande avbrutet",
    "utfardad": "Utfärdad",
    "atgarder_oppna": "Åtgärder öppna",
    "ombesiktning": "Ombesiktning",
}

_READ_ERRORS = (OSError, ValueError, KeyError, TypeError)


def derive_status(
    *,
    planned: bool,
    has_snapshot: bool,
    field_completed: bool,
    ready_to_issue: bool,
    issuance_interrupted: bool,
    issued: bool,
    deficiencies: bool,
    reinspection: CaseStatus | None,
) -> str:
    """Visningsstatus för ett uppdrag, härledd ur befintliga uppgifter.

    ``issued`` betyder att uppdraget har ett intyg med ställningen ``current``.
    ``ready_to_issue`` betyder att posten är protokollklar och att
    protokollkällan fortfarande svarar mot fältets ögonblicksbild.
    ``reinspection`` är status för uppdragets senaste ombesiktningsärende, eller
    ``None`` om inget finns. Levererad saknas tills leveranser registreras.
    """
    if issued:
        if reinspection in (CaseStatus.OPEN, CaseStatus.READY):
            return "ombesiktning"
        if deficiencies and reinspection is None:
            return "atgarder_oppna"
        return "utfardad"
    if issuance_interrupted:
        return "utfardande_avbrutet"
    if has_snapshot and not field_completed:
        return "pagaende"
    if ready_to_issue:
        return "leveransklar"
    if field_completed:
        return "att_granska"
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
            except _READ_ERRORS:
                cache[inspector_id] = None
        return cache[inspector_id]

    @router.get("/api/ovk/uppdrag", response_model=None)
    def list_assignments(request: Request) -> dict[str, Any]:
        actor = current_actor(request)
        items: list[dict[str, Any]] = []
        unreadable: list[dict[str, str]] = []
        names: dict[str, str | None] = {}

        def skip(project_id: str, inspection_id: str, reason: str) -> None:
            unreadable.append(
                {"project_id": project_id, "inspection_id": inspection_id, "orsak": reason}
            )

        for project_id in visible_project_ids(data_root, actor):
            directory = data_root / "projects" / project_id / "ovk"
            if not directory.is_dir():
                continue
            try:
                project_properties = properties.list(project_id)
                project_certificates = certificates.list(project_id)
                project_cases = reinspections.list(project_id)
            except _READ_ERRORS:
                # Intyg och ärenden avgör status, och fastigheten avgör vad
                # raden säger sig gälla. Hellre ett redovisat läsfel för hela
                # projektet än rader som påstår något osant.
                skip(project_id, "", "projekt")
                continue
            if any(item.project_id != project_id for item in project_certificates):
                skip(project_id, "", "intyg")
                continue
            for path in sorted(directory.glob("*.json")):
                try:
                    record = workflows.load(project_id, path.stem)
                except _READ_ERRORS:
                    skip(project_id, path.stem, "post")
                    continue
                inspection_id = record.inspection.inspection_id
                if inspection_id != path.stem or (
                    record.inspection.ovk_object.project_id != project_id
                ):
                    # Postens innehåll styr vilka filer som läses härnäst. Det
                    # måste därför stämma med platsen posten ligger på.
                    skip(project_id, path.stem, "identitet")
                    continue
                field = _field_state(data_root, project_id, inspection_id)
                if isinstance(field, str):
                    skip(project_id, inspection_id, field)
                    continue
                own = tuple(
                    item for item in project_certificates if item.inspection_id == inspection_id
                )
                current = [
                    item
                    for item in own
                    if intyg_standing(data_root, certificates, item).get("status") == "current"
                ]
                if own and len(current) != 1:
                    skip(project_id, inspection_id, "intyg")
                    continue
                items.append(
                    _assignment(
                        data_root,
                        record,
                        field=field,
                        properties=project_properties,
                        certificate=current[0] if current else None,
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


def _field_state(data_root: Path, project_id: str, inspection_id: str) -> dict[str, Any] | str:
    """Fältets läge ur ögonblicksbilden, eller orsaken till att det inte kan anges."""
    path = data_root / "projects" / project_id / "ovk-field" / inspection_id / "snapshot.json"
    if not path.is_file():
        if (data_root / "ovk-field-sync" / f"{inspection_id}.json").exists():
            # Äldre fältdata som ännu inte flyttats in under projektet. Utan
            # den här kontrollen skulle uppdraget se ut att sakna fältarbete.
            return "omigrerad"
        return {"synkad": False, "ogonblicksbild_andrad": None, "avslutat": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except (OSError, ValueError):
        return "falt"
    if not isinstance(payload, dict) or payload.get("inspection_id") != inspection_id:
        return "falt"
    completed = payload.get("field_work_completed_at")
    return {
        "synkad": True,
        # Tiden då filen senast skrevs. En synk utan ändrat innehåll skriver
        # inte om filen, så detta är inte tiden för senaste synkförsök.
        "ogonblicksbild_andrad": modified.isoformat(timespec="seconds"),
        "avslutat": completed if isinstance(completed, str) and completed else None,
    }


def _assignment(
    data_root: Path,
    record: OvkWorkflowRecord,
    *,
    field: dict[str, Any],
    properties: tuple[Fastighet, ...],
    certificate: OvkIntyg | None,
    cases: tuple[OvkReinspectionCase, ...],
    inspector: str | None,
) -> dict[str, Any]:
    inspection = record.inspection
    obj = inspection.ovk_object
    project_id = obj.project_id
    inspection_id = inspection.inspection_id
    fastighet = next((item for item in properties if item.fastighet_id == obj.object_id), None)
    byggnad = (
        next((b for b in fastighet.byggnader if b.byggnad_id == obj.building_id), None)
        if fastighet
        else None
    )
    own_cases = sorted(
        (case for case in cases if case.source_inspection_id == inspection_id),
        key=lambda case: (case.opened_at, case.case_id),
    )
    issued = certificate is not None
    status = derive_status(
        planned=record.planning is not None,
        has_snapshot=bool(field["synkad"]),
        field_completed=field["avslutat"] is not None,
        ready_to_issue=(
            not issued
            and record.protocol_ready
            and protocol_source_is_current(data_root, project_id, inspection_id, record)
        ),
        issuance_interrupted=(
            not issued and manifest_path(data_root, project_id, inspection_id).exists()
        ),
        issued=issued,
        deficiencies=inspection.conclusion is InspectionConclusion.DEFICIENCIES,
        reinspection=own_cases[-1].status if own_cases else None,
    )
    planning = record.planning
    return {
        "project_id": project_id,
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
        "intyg_id": certificate.intyg_id if certificate else None,
        "utfardat": certificate.issued_date.isoformat() if certificate else None,
        "nasta_steg": _next_step(status, project_id, inspection_id),
    }


def _address(fastighet: Fastighet) -> str | None:
    adress = fastighet.byggnadens_adress
    parts = [adress.gata.strip(), " ".join(p for p in (adress.postnr, adress.ort) if p).strip()]
    text = ", ".join(part for part in parts if part)
    return text or None


def _next_step(status: str, project_id: str, inspection_id: str) -> dict[str, str]:
    """Nästa steg som text och länk.

    Alla länkar bär ``project_id`` och ``inspection_id``. ``/ovk/besiktning`` och
    ``/ovk/falt`` läser dem i dag; ``/ovk/intyg`` och ``/ovk/ombesiktning`` gör
    det först när de flyttas in i skrivbordsskalet.
    """
    query = (
        f"?project_id={quote(project_id, safe='')}&inspection_id={quote(inspection_id, safe='')}"
    )
    steps: dict[str, tuple[str, str]] = {
        "ej_planerad": ("Planera", "/ovk/besiktning"),
        "planerad": ("Öppna i fält", "/ovk/falt"),
        "pagaende": ("Följ fältarbetet", "/ovk/besiktning"),
        "att_granska": ("Granska", "/ovk/besiktning"),
        "leveransklar": ("Utfärda intyg", "/ovk/intyg"),
        "utfardande_avbrutet": ("Återuppta utfärdandet", "/ovk/intyg"),
        "utfardad": ("Visa intyg", "/ovk/intyg"),
        "atgarder_oppna": ("Öppna ombesiktning", "/ovk/ombesiktning"),
        "ombesiktning": ("Följ ombesiktning", "/ovk/ombesiktning"),
    }
    text, page = steps[status]
    return {"text": text, "href": page + query}
