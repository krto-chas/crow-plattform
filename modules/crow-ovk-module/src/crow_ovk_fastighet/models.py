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

import re
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


_KUND_ID = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
_KUND_TEXT_LIMIT = 200


def normalize_organisationsnummer(value: str) -> str:
    """Skriv ett organisationsnummer som NNNNNN-NNNN.

    Godtar tio siffror, eller tolv där de två första är sekel (16, 18, 19, 20),
    med valfritt bindestreck eller blanktecken före de fyra sista. Tomt förblir
    tomt. Annat lämnas orört, så att valideringen kan avvisa det.

    Seklet lagras inte. Ett personnummer skrivet med plustecken (person över
    hundra år) godtas därför inte; det är en känd begränsning.
    """
    text = "".join(value.split())
    if not text:
        return ""
    match = re.fullmatch(r"(?:16|18|19|20)?([0-9]{6})-?([0-9]{4})", text, re.ASCII)
    if match is None:
        return value.strip()
    return f"{match.group(1)}-{match.group(2)}"


def is_organisationsnummer(value: str) -> bool:
    """Sant för NNNNNN-NNNN med riktig kontrollsiffra (Luhn), utom enbart nollor."""
    if not re.fullmatch(r"[0-9]{6}-[0-9]{4}", value, re.ASCII) or value == "000000-0000":
        return False
    total = 0
    for index, char in enumerate(value.replace("-", "")):
        digit = int(char) * (2 if index % 2 == 0 else 1)
        total += digit - 9 if digit > 9 else digit
    return total % 10 == 0


@dataclass(frozen=True, slots=True)
class Kund:
    """Den som besiktningen görs åt: beställaren eller fastighetsägaren.

    Kunden är gemensam för organisationen och inte bunden till ett projekt.
    I koden heter den ``kund``; ``customer`` är organisationen som använder Crow.
    """

    kund_id: str
    namn: str
    kontaktperson: str = ""
    telefon: str = ""
    epost: str = ""
    postadress: Adress = field(default_factory=Adress)
    faktureringsadress: Adress = field(default_factory=Adress)
    referens: str = ""
    updated_at: str = ""
    updated_by: str | None = None
    # Organisationsnummer i formen NNNNNN-NNNN, eller tomt. Frivilligt. För
    # enskild firma är det ett personnummer och ska hanteras som personuppgift.
    organisationsnummer: str = ""

    def __post_init__(self) -> None:
        if self.organisationsnummer and not is_organisationsnummer(self.organisationsnummer):
            raise ValueError("organisationsnummer is not valid")
        if not _KUND_ID.fullmatch(self.kund_id):
            raise ValueError("invalid kund_id")
        if not self.namn.strip():
            raise ValueError("kundens namn must not be empty")
        for label, value in (
            ("namn", self.namn),
            ("kontaktperson", self.kontaktperson),
            ("telefon", self.telefon),
            ("epost", self.epost),
            ("referens", self.referens),
        ):
            if len(value) > _KUND_TEXT_LIMIT:
                raise ValueError(f"{label} is too long")
            if any(ord(char) < 32 for char in value):
                raise ValueError(f"{label} must be a single line")
        if self.epost and ("@" not in self.epost or any(c.isspace() for c in self.epost)):
            raise ValueError("epost is not an e-mail address")


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
    # Kunden (beställaren) som fastigheten hör till, eller None. Byggnadsägare
    # och förvaltare ligger kvar som egna uppgifter på fastigheten.
    kund_id: str | None = None

    def __post_init__(self) -> None:
        if self.kund_id is not None and not _KUND_ID.fullmatch(self.kund_id):
            raise ValueError("invalid kund_id")
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
        # Utelämnas utan kund, så att äldre poster serialiseras oförändrat.
        **({"kund_id": fastighet.kund_id} if fastighet.kund_id is not None else {}),
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
        kund_id=_optional_id(payload.get("kund_id"), "kund_id"),
    )


def _optional_id(value: object, label: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def kund_to_payload(kund: Kund) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kund_id": kund.kund_id,
        "namn": kund.namn,
        "kontaktperson": kund.kontaktperson,
        "telefon": kund.telefon,
        "epost": kund.epost,
        "postadress": _adress_to_payload(kund.postadress),
        "faktureringsadress": _adress_to_payload(kund.faktureringsadress),
        "referens": kund.referens,
        # Utelämnas när det saknas, så att äldre kundposter behåller sin revision.
        **({"organisationsnummer": kund.organisationsnummer} if kund.organisationsnummer else {}),
        "updated_at": kund.updated_at,
        "updated_by": kund.updated_by,
    }


def _kund_text(payload: dict[str, object], key: str) -> str:
    """Ett textfält i kundposten. Saknat eller null är tomt; annat än text avvisas."""
    value = payload.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value.strip()


def _kund_adress(payload: dict[str, object], key: str) -> Adress:
    value = payload.get(key)
    if value is None:
        return Adress()
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    adress = Adress(
        gata=_kund_text(value, "gata"),
        postnr=_kund_text(value, "postnr"),
        ort=_kund_text(value, "ort"),
    )
    for part in (adress.gata, adress.postnr, adress.ort):
        if len(part) > _KUND_TEXT_LIMIT:
            raise ValueError(f"{key} is too long")
        if any(ord(char) < 32 for char in part):
            raise ValueError(f"{key} must be single lines")
    return adress


def kund_from_payload(payload: dict[str, object]) -> Kund:
    updated_by = payload.get("updated_by")
    kund_id = payload.get("kund_id")
    if not isinstance(kund_id, str):
        raise ValueError("kund_id must be a string")
    return Kund(
        # Id:t klipps inte: det ska stämma tecken för tecken med adressen och
        # filnamnet, och ett id med blanktecken avvisas av valideringen.
        kund_id=kund_id,
        namn=_kund_text(payload, "namn"),
        kontaktperson=_kund_text(payload, "kontaktperson"),
        telefon=_kund_text(payload, "telefon"),
        epost=_kund_text(payload, "epost"),
        postadress=_kund_adress(payload, "postadress"),
        faktureringsadress=_kund_adress(payload, "faktureringsadress"),
        referens=_kund_text(payload, "referens"),
        organisationsnummer=normalize_organisationsnummer(
            _kund_text(payload, "organisationsnummer")
        ),
        updated_at=_kund_text(payload, "updated_at"),
        updated_by=updated_by if isinstance(updated_by, str) and updated_by else None,
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
