"""Fastighetsregister för OVK:s skrivbordsarbetsplats.

En rutt som ger organisationens fastigheter i ett svar, över alla synliga
projekt. Fastigheterna ägs fortfarande av OVK-registret per projekt (ADR-012):
rutten läser, den flyttar eller slår inte ihop något. Två registerposter med
samma beteckning och ort pekas ut så att användaren kan välja rätt, aldrig
sammanfogas tyst.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

from crow_ovk_fastighet import Fastighet, FastighetRepository
from fastapi import APIRouter, Request

from crow_ovk_intyg import OvkIntyg, OvkIntygRepository
from crow_ovk_workflow import OvkWorkflowRepository

from .ovk_certificate_status import intyg_standing
from .ovk_scope import current_actor, visible_project_ids

_READ_ERRORS = (OSError, ValueError, KeyError, TypeError)


def normalize_designation(value: str) -> str:
    """Motsvarar normaliseringen i fastighetssökningen i flödet för ny besiktning."""
    text = unicodedata.normalize("NFKC", value).strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*:\s*", ":", text)
    return text.casefold()


def ovk_property_register_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    properties = FastighetRepository(data_root)
    workflows = OvkWorkflowRepository(data_root)
    certificates = OvkIntygRepository(data_root)

    @router.get("/api/ovk/fastigheter", response_model=None)
    def list_properties(request: Request) -> dict[str, Any]:
        actor = current_actor(request)
        items: list[dict[str, Any]] = []
        unreadable: list[dict[str, str]] = []
        for project_id in visible_project_ids(data_root, actor):
            if not (data_root / "projects" / project_id / "fastighet").is_dir():
                continue
            try:
                project_properties = properties.list(project_id)
                project_records = workflows.list(project_id)
                project_certificates = certificates.list(project_id)
            except _READ_ERRORS:
                # Utan besiktningar och intyg kan raden inte säga när fastigheten
                # senast besiktades. Hellre ett redovisat läsfel än en gissning.
                unreadable.append({"project_id": project_id, "orsak": "projekt"})
                continue
            if any(item.project_id != project_id for item in project_properties):
                unreadable.append({"project_id": project_id, "orsak": "identitet"})
                continue
            current = [
                item
                for item in project_certificates
                if item.project_id == project_id
                and intyg_standing(data_root, certificates, item).get("status") == "current"
            ]
            inspections_per_object: dict[str, list[str]] = {}
            for record in project_records:
                obj = record.inspection.ovk_object
                inspections_per_object.setdefault(obj.object_id, []).append(
                    record.inspection.inspection_id
                )
            for fastighet in project_properties:
                own_inspections = inspections_per_object.get(fastighet.fastighet_id, [])
                own_certificates = [
                    item for item in current if item.inspection_id in own_inspections
                ]
                items.append(_property(fastighet, len(own_inspections), own_certificates))
        occurrences: dict[tuple[str, str], int] = {}
        for item in items:
            occurrences[item["_nyckel"]] = occurrences.get(item["_nyckel"], 0) + 1
        for item in items:
            item["forekomster"] = occurrences[item.pop("_nyckel")]
        items.sort(key=lambda item: (item["fastighetsbeteckning"].casefold(), item["project_id"]))
        return {
            "fastigheter": items,
            "ej_lasbara": unreadable,
            "fullstandig": not unreadable,
        }

    return router


def _property(
    fastighet: Fastighet, inspection_count: int, certificates: list[OvkIntyg]
) -> dict[str, Any]:
    adress = fastighet.byggnadens_adress
    latest = max(certificates, key=lambda item: (item.issued_date, item.intyg_id), default=None)
    # Varje byggnads frist följer av dess senaste intyg, inte av äldre intyg
    # som fortfarande är gällande för sin besiktning.
    latest_per_building: dict[str, OvkIntyg] = {}
    for item in sorted(certificates, key=lambda item: (item.issued_date, item.intyg_id)):
        latest_per_building[item.building_id] = item
    due_dates: list[date] = [
        item.next_inspection.due_date
        for item in latest_per_building.values()
        if item.next_inspection.due_date is not None
    ]
    return {
        "project_id": fastighet.project_id,
        "fastighet_id": fastighet.fastighet_id,
        "fastighetsbeteckning": fastighet.fastighetsbeteckning,
        "gata": adress.gata or None,
        "postnr": adress.postnr or None,
        "ort": adress.ort or None,
        "byggnadsagare": fastighet.byggnadsagare_namn or None,
        "fastighetstyp": fastighet.fastighetstyp.value,
        "byggnader": [
            {"byggnad_id": byggnad.byggnad_id, "namn": byggnad.internt_namn}
            for byggnad in fastighet.byggnader
        ],
        "antal_besiktningar": inspection_count,
        "senast_utfardat": latest.issued_date.isoformat() if latest else None,
        # Tidigaste fristen bland byggnaderna: den som först kräver handling.
        "nasta_besiktning": min(due_dates).isoformat() if due_dates else None,
        "_nyckel": (
            normalize_designation(fastighet.fastighetsbeteckning),
            adress.ort.strip().casefold(),
        ),
    }
