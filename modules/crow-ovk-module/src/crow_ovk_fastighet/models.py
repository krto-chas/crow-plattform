"""Fastighetsentitet och besiktningsmannaregister (pass 102).

Fältstrukturen följer protokollmallens A-del (se docs/ovk-protokollmallar.md):
fastighetsbeteckning, adresser, byggnadsägare, faktureringsadress, förvaltare
och byggnader med BRA och enhetsantal. Besiktningsmannen är en registrerad
resurs med behörighet N/K enligt BFS 2011:16 och certifieringsuppgifter,
och kan omsättas till intygets Funktionskontrollant utan omskrivning.

Alla uppgifter är STATED av kontoret eller besiktningsmannen; inget härleds.
BRA lagras som Decimal och serialiseras som sträng enligt ADR-0009.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum

SCHEMA_VERSION = "crow-ovk-fastighet-v0.1"


class Fastighetstyp(StrEnum):
    """Styr besiktningsflödet i fält: flerbostadshus kör lägenhetslista,
    övriga typer går direkt in i objektbesiktningen."""

    VILLA = "villa"
    FLERBOSTADSHUS = "flerbostadshus"
    KONTORSBYGGNAD = "kontorsbyggnad"
    INDUSTRIFASTIGHET = "industrifastighet"


class Behorighet(StrEnum):
    """Behörighetsnivå för funktionskontrollant enligt BFS 2011:16."""

    N = "N"
    K = "K"


@dataclass(frozen=True, slots=True)
class Adress:
    gata: str = ""
    postnr: str = ""
    ort: str = ""

    @property
    def is_empty(self) -> bool:
        return not (self.gata.strip() or self.postnr.strip() or self.ort.strip())


@dataclass(frozen=True, slots=True)
class Forvaltare:
    namn: str = ""
    telefon: str = ""
    epost: str = ""


@dataclass(frozen=True, slots=True)
class Byggnad:
    byggnad_id: str
    internt_namn: str
    internt_nr: str = ""
    verksamhet: str = ""
    bra_m2: Decimal | None = None
    antal_lagenheter: int | None = None
    antal_lokaler: int | None = None

    def __post_init__(self) -> None:
        if not self.byggnad_id.strip():
            raise ValueError("byggnad_id must not be empty")
        if not self.internt_namn.strip():
            raise ValueError("byggnad internt_namn must not be empty")
        if self.bra_m2 is not None and self.bra_m2 < 0:
            raise ValueError("bra_m2 cannot be negative")
        for label, value in (
            ("antal_lagenheter", self.antal_lagenheter),
            ("antal_lokaler", self.antal_lokaler),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{label} cannot be negative")


@dataclass(frozen=True, slots=True)
class Fastighet:
    fastighet_id: str
    project_id: str
    fastighetsbeteckning: str
    referensnr: str = ""
    byggnadens_adress: Adress = field(default_factory=Adress)
    byggnadsagare_namn: str = ""
    byggnadsagare_adress: Adress = field(default_factory=Adress)
    faktureringsadress: Adress = field(default_factory=Adress)
    forvaltare: Forvaltare = field(default_factory=Forvaltare)
    fastighetstyp: Fastighetstyp = Fastighetstyp.FLERBOSTADSHUS
    byggnader: tuple[Byggnad, ...] = ()
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.fastighet_id.strip():
            raise ValueError("fastighet_id must not be empty")
        if not self.project_id.strip():
            raise ValueError("project_id must not be empty")
        if not self.fastighetsbeteckning.strip():
            raise ValueError("fastighetsbeteckning must not be empty")
        seen: set[str] = set()
        for byggnad in self.byggnader:
            if byggnad.byggnad_id in seen:
                raise ValueError(f"duplicate byggnad_id {byggnad.byggnad_id!r}")
            seen.add(byggnad.byggnad_id)


@dataclass(frozen=True, slots=True)
class Besiktningsman:
    """Registrerad besiktningsmannaresurs med certifiering (STATED)."""

    besiktningsman_id: str
    namn: str
    behorighet: Behorighet
    certifieringsorgan: str
    certnummer: str
    giltig_till: date | None = None
    telefon: str = ""
    epost: str = ""
    foretag: str = ""
    adress: Adress = field(default_factory=Adress)

    def __post_init__(self) -> None:
        if not self.besiktningsman_id.strip():
            raise ValueError("besiktningsman_id must not be empty")
        if not self.namn.strip():
            raise ValueError("besiktningsman namn must not be empty")
        if not self.certifieringsorgan.strip():
            raise ValueError("certifieringsorgan must not be empty")
        if not self.certnummer.strip():
            raise ValueError("certnummer must not be empty")


def _decimal_from(value: object, label: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a decimal string") from exc


def _int_from(value: object, label: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ValueError(f"{label} must be an integer")
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer") from exc


def _adress_to_payload(adress: Adress) -> dict[str, str]:
    return {"gata": adress.gata, "postnr": adress.postnr, "ort": adress.ort}


def _adress_from_payload(value: object) -> Adress:
    if value is None:
        return Adress()
    if not isinstance(value, dict):
        raise ValueError("adress must be an object")
    return Adress(
        gata=str(value.get("gata", "")),
        postnr=str(value.get("postnr", "")),
        ort=str(value.get("ort", "")),
    )


def fastighet_to_payload(fastighet: Fastighet) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "fastighet_id": fastighet.fastighet_id,
        "project_id": fastighet.project_id,
        "fastighetsbeteckning": fastighet.fastighetsbeteckning,
        "referensnr": fastighet.referensnr,
        "byggnadens_adress": _adress_to_payload(fastighet.byggnadens_adress),
        "byggnadsagare_namn": fastighet.byggnadsagare_namn,
        "byggnadsagare_adress": _adress_to_payload(fastighet.byggnadsagare_adress),
        "faktureringsadress": _adress_to_payload(fastighet.faktureringsadress),
        "fastighetstyp": fastighet.fastighetstyp.value,
        "forvaltare": {
            "namn": fastighet.forvaltare.namn,
            "telefon": fastighet.forvaltare.telefon,
            "epost": fastighet.forvaltare.epost,
        },
        "byggnader": [
            {
                "byggnad_id": byggnad.byggnad_id,
                "internt_namn": byggnad.internt_namn,
                "internt_nr": byggnad.internt_nr,
                "verksamhet": byggnad.verksamhet,
                "bra_m2": str(byggnad.bra_m2) if byggnad.bra_m2 is not None else None,
                "antal_lagenheter": byggnad.antal_lagenheter,
                "antal_lokaler": byggnad.antal_lokaler,
            }
            for byggnad in fastighet.byggnader
        ],
        "updated_at": fastighet.updated_at,
    }


def fastighet_from_payload(payload: dict[str, object]) -> Fastighet:
    raw_byggnader = payload.get("byggnader", [])
    if not isinstance(raw_byggnader, list):
        raise ValueError("byggnader must be a list")
    byggnader: list[Byggnad] = []
    for item in raw_byggnader:
        if not isinstance(item, dict):
            raise ValueError("byggnad entries must be objects")
        byggnader.append(
            Byggnad(
                byggnad_id=str(item.get("byggnad_id", "")),
                internt_namn=str(item.get("internt_namn", "")),
                internt_nr=str(item.get("internt_nr", "")),
                verksamhet=str(item.get("verksamhet", "")),
                bra_m2=_decimal_from(item.get("bra_m2"), "bra_m2"),
                antal_lagenheter=_int_from(item.get("antal_lagenheter"), "antal_lagenheter"),
                antal_lokaler=_int_from(item.get("antal_lokaler"), "antal_lokaler"),
            )
        )
    forvaltare_payload = payload.get("forvaltare") or {}
    if not isinstance(forvaltare_payload, dict):
        raise ValueError("forvaltare must be an object")
    return Fastighet(
        fastighet_id=str(payload.get("fastighet_id", "")),
        project_id=str(payload.get("project_id", "")),
        fastighetsbeteckning=str(payload.get("fastighetsbeteckning", "")),
        referensnr=str(payload.get("referensnr", "")),
        byggnadens_adress=_adress_from_payload(payload.get("byggnadens_adress")),
        byggnadsagare_namn=str(payload.get("byggnadsagare_namn", "")),
        byggnadsagare_adress=_adress_from_payload(payload.get("byggnadsagare_adress")),
        faktureringsadress=_adress_from_payload(payload.get("faktureringsadress")),
        fastighetstyp=Fastighetstyp(
            str(payload.get("fastighetstyp", Fastighetstyp.FLERBOSTADSHUS.value))
        ),
        forvaltare=Forvaltare(
            namn=str(forvaltare_payload.get("namn", "")),
            telefon=str(forvaltare_payload.get("telefon", "")),
            epost=str(forvaltare_payload.get("epost", "")),
        ),
        byggnader=tuple(byggnader),
        updated_at=str(payload.get("updated_at", "")),
    )


def besiktningsman_to_payload(person: Besiktningsman) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "besiktningsman_id": person.besiktningsman_id,
        "namn": person.namn,
        "behorighet": person.behorighet.value,
        "certifieringsorgan": person.certifieringsorgan,
        "certnummer": person.certnummer,
        "giltig_till": person.giltig_till.isoformat() if person.giltig_till else None,
        "telefon": person.telefon,
        "epost": person.epost,
        "foretag": person.foretag,
        "adress": _adress_to_payload(person.adress),
    }


def besiktningsman_from_payload(payload: dict[str, object]) -> Besiktningsman:
    giltig_raw = payload.get("giltig_till")
    giltig_till = date.fromisoformat(str(giltig_raw)) if giltig_raw else None
    return Besiktningsman(
        besiktningsman_id=str(payload.get("besiktningsman_id", "")),
        namn=str(payload.get("namn", "")),
        behorighet=Behorighet(str(payload.get("behorighet", ""))),
        certifieringsorgan=str(payload.get("certifieringsorgan", "")),
        certnummer=str(payload.get("certnummer", "")),
        giltig_till=giltig_till,
        telefon=str(payload.get("telefon", "")),
        epost=str(payload.get("epost", "")),
        foretag=str(payload.get("foretag", "")),
        adress=_adress_from_payload(payload.get("adress")),
    )
