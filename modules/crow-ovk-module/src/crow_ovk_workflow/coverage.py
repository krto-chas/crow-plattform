"""Besiktningstäckning: alla fläktar/aggregat måste adresseras explicit.

En OVK kan aldrig markeras komplett utan att varje aggregat i systemförteckningen
har fått ett uttryckligt ställningstagande. "Ej besiktigad" kräver skriftlig
motivering, STATED av besiktningsmannen. Fastighetsnivåstatusen härleds
deterministiskt ur aggregatstatusarna och systemförteckningens bekräftelse.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AggregatStatus(StrEnum):
    BESIKTIGAD = "besiktigad"
    EJ_BESIKTIGAD = "ej_besiktigad"
    EJ_TILLAMPLIG = "ej_tillamplig"


class BekraftelseRoll(StrEnum):
    BESIKTNINGSMAN = "besiktningsman"
    BYGGNADSAGARE = "byggnadsagare"


class FastighetsnivaStatus(StrEnum):
    SAMTLIGA_BESIKTADE = "samtliga_besiktade"
    DELVIS_BESIKTADE = "delvis_besiktade"
    SYSTEMFORTECKNING_EJ_BEKRAFTAD = "systemforteckning_ej_bekraftad"


@dataclass(frozen=True, slots=True)
class AggregatCoverage:
    """Ställningstagande för ett aggregat. Motiveringen är STATED, aldrig härledd."""

    aggregat_id: str
    label: str
    status: AggregatStatus
    justification: str = ""
    stated_by: str = ""

    def __post_init__(self) -> None:
        if not self.aggregat_id.strip():
            raise ValueError("aggregat_id must not be empty")
        if not self.label.strip():
            raise ValueError("aggregat label must not be empty")
        if self.status is AggregatStatus.EJ_BESIKTIGAD:
            if not self.justification.strip():
                raise ValueError(
                    f"aggregat {self.label!r} marked ej_besiktigad requires a written "
                    "justification stated by the inspector"
                )
            if not self.stated_by.strip():
                raise ValueError(
                    f"aggregat {self.label!r} marked ej_besiktigad requires stated_by "
                    "(the inspector stating the justification)"
                )


@dataclass(frozen=True, slots=True)
class SystemForteckningBekraftelse:
    """Bekräftelse att systemförteckningen är komplett. STATED av angiven roll."""

    confirmed_by: str
    role: BekraftelseRoll

    def __post_init__(self) -> None:
        if not self.confirmed_by.strip():
            raise ValueError("system list confirmation requires confirmed_by")


@dataclass(frozen=True, slots=True)
class InspectionCoverage:
    inspection_id: str
    aggregat: tuple[AggregatCoverage, ...] = ()
    system_list_confirmation: SystemForteckningBekraftelse | None = None

    def __post_init__(self) -> None:
        if not self.inspection_id.strip():
            raise ValueError("inspection_id must not be empty")
        seen: set[str] = set()
        for item in self.aggregat:
            if item.aggregat_id in seen:
                raise ValueError(f"duplicate aggregat_id {item.aggregat_id!r} in coverage")
            seen.add(item.aggregat_id)

    @property
    def uninspected(self) -> tuple[AggregatCoverage, ...]:
        return tuple(item for item in self.aggregat if item.status is AggregatStatus.EJ_BESIKTIGAD)

    @property
    def is_delbesiktning(self) -> bool:
        """Delar av systemet har lämnats obesiktigade."""
        return bool(self.uninspected)

    @property
    def fastighetsniva(self) -> FastighetsnivaStatus:
        if self.system_list_confirmation is None:
            return FastighetsnivaStatus.SYSTEMFORTECKNING_EJ_BEKRAFTAD
        if self.is_delbesiktning:
            return FastighetsnivaStatus.DELVIS_BESIKTADE
        return FastighetsnivaStatus.SAMTLIGA_BESIKTADE


class CoverageError(ValueError):
    """Täckningskravet är inte uppfyllt; protokoll/intyg kan inte färdigställas."""


def validate_coverage_for_finalization(coverage: InspectionCoverage | None) -> None:
    """Grind före protokoll/intyg: alla aggregat explicit adresserade.

    Modellinvarianterna garanterar redan motivering för ej_besiktigad; här
    valideras att täckning finns alls och att den inte är tom, eftersom en
    tom förteckning betyder att fläktar/aggregat aldrig adresserats.
    """
    if coverage is None:
        raise CoverageError(
            "besiktningstäckning saknas: alla fläktar/aggregat måste adresseras "
            "innan protokoll eller intyg kan färdigställas"
        )
    if not coverage.aggregat:
        raise CoverageError(
            "besiktningstäckningen är tom: minst ett aggregat måste registreras "
            "med explicit status (besiktigad / ej besiktigad / ej tillämplig)"
        )


def coverage_to_payload(coverage: InspectionCoverage) -> dict[str, object]:
    confirmation = coverage.system_list_confirmation
    return {
        "inspection_id": coverage.inspection_id,
        "aggregat": [
            {
                "aggregat_id": item.aggregat_id,
                "label": item.label,
                "status": item.status.value,
                "justification": item.justification,
                "stated_by": item.stated_by,
            }
            for item in coverage.aggregat
        ],
        "system_list_confirmation": (
            {"confirmed_by": confirmation.confirmed_by, "role": confirmation.role.value}
            if confirmation is not None
            else None
        ),
        "fastighetsniva": coverage.fastighetsniva.value,
        "is_delbesiktning": coverage.is_delbesiktning,
    }


def coverage_from_payload(payload: dict[str, object]) -> InspectionCoverage:
    inspection_id = payload.get("inspection_id")
    if not isinstance(inspection_id, str):
        raise ValueError("coverage.inspection_id must be a string")
    raw_aggregat = payload.get("aggregat")
    if not isinstance(raw_aggregat, list):
        raise ValueError("coverage.aggregat must be a list")
    aggregat: list[AggregatCoverage] = []
    for item in raw_aggregat:
        if not isinstance(item, dict):
            raise ValueError("coverage.aggregat entries must be objects")
        aggregat.append(
            AggregatCoverage(
                aggregat_id=str(item.get("aggregat_id", "")),
                label=str(item.get("label", "")),
                status=AggregatStatus(str(item.get("status", ""))),
                justification=str(item.get("justification", "")),
                stated_by=str(item.get("stated_by", "")),
            )
        )
    confirmation_payload = payload.get("system_list_confirmation")
    confirmation: SystemForteckningBekraftelse | None = None
    if confirmation_payload is not None:
        if not isinstance(confirmation_payload, dict):
            raise ValueError("coverage.system_list_confirmation must be an object")
        confirmation = SystemForteckningBekraftelse(
            confirmed_by=str(confirmation_payload.get("confirmed_by", "")),
            role=BekraftelseRoll(str(confirmation_payload.get("role", ""))),
        )
    return InspectionCoverage(
        inspection_id=inspection_id,
        aggregat=tuple(aggregat),
        system_list_confirmation=confirmation,
    )
