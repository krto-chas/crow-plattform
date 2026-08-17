"""Domänmodeller för OVK-intyg enligt plan- och bygglagstiftningen och BFS 2011:16."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from crow_ovk import EvidenceOrigin
from crow_ovk_pricing import InspectionType
from crow_ovk_workflow import AggregatCoverage, FastighetsnivaStatus

SCHEMA_VERSION = "crow-ovk-intyg-v0.1"


class IntygResult(StrEnum):
    GODKAND = "godkand"
    EJ_GODKAND = "ej_godkand"


class Behorighet(StrEnum):
    N = "N"
    K = "K"


@dataclass(frozen=True, slots=True)
class Funktionskontrollant:
    name: str
    behorighet: Behorighet
    certification_body: str
    certificate_number: str
    certificate_valid_to: date | None = None


@dataclass(frozen=True, slots=True)
class Byggnadsagare:
    name: str
    contact: str | None = None


@dataclass(frozen=True, slots=True)
class IntygSystemRow:
    system_id: str
    system_type: str
    label: str
    result: IntygResult


@dataclass(frozen=True, slots=True)
class NextInspection:
    """Nästa besiktningsfrist. Alltid härledd — därför obligatorisk skriven basis."""

    interval_years: int | None
    due_date: date | None
    origin: EvidenceOrigin
    basis: str

    def __post_init__(self) -> None:
        if self.origin is EvidenceOrigin.INFERRED and not self.basis.strip():
            raise ValueError("inferred next inspection requires a written basis")


@dataclass(frozen=True, slots=True)
class OvkIntyg:
    intyg_id: str
    inspection_id: str
    project_id: str
    building_id: str
    object_name: str
    fastighetsbeteckning: str
    byggnadsagare: Byggnadsagare
    funktionskontrollant: Funktionskontrollant
    inspection_type: InspectionType
    inspection_date: date
    issued_date: date
    systems: tuple[IntygSystemRow, ...]
    result: IntygResult
    next_inspection: NextInspection
    address: str | None = None
    delbesiktning: bool = False
    fastighetsniva: FastighetsnivaStatus = FastighetsnivaStatus.SYSTEMFORTECKNING_EJ_BEKRAFTAD
    uninspected_aggregat: tuple[AggregatCoverage, ...] = ()

    def __post_init__(self) -> None:
        if not self.intyg_id.strip():
            raise ValueError("intyg_id is required")
        if not self.fastighetsbeteckning.strip():
            raise ValueError("fastighetsbeteckning is required")
        if self.issued_date < self.inspection_date:
            raise ValueError("issued_date cannot precede inspection_date")
        if self.delbesiktning != bool(self.uninspected_aggregat):
            raise ValueError(
                "delbesiktningsmarkering och listan över ej besiktigade aggregat "
                "måste vara konsistenta"
            )
        if self.delbesiktning and self.fastighetsniva is FastighetsnivaStatus.SAMTLIGA_BESIKTADE:
            raise ValueError("intyg med delbesiktningsmarkering kan inte hävda samtliga_besiktade")
