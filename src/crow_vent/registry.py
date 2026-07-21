from __future__ import annotations

import re

from .models import VentComponentDefinition

_COMPONENTS = (
    VentComponentDefinition(
        "TD", "Tilluftsdon", "terminal", "supply", ("T", "TLD"), "Tillför luft till rum eller zon."
    ),
    VentComponentDefinition(
        "FD",
        "Frånluftsdon",
        "terminal",
        "extract",
        ("F", "FLD"),
        "För bort luft från rum eller zon.",
    ),
    VentComponentDefinition(
        "ÖD",
        "Överluftsdon",
        "terminal",
        "transfer",
        ("OD", "ÖL"),
        "Överför luft mellan rum eller zoner.",
    ),
    VentComponentDefinition(
        "UTD", "Uteluftsdon", "terminal", "outdoor", ("UL", "ULG"), "Tar in uteluft."
    ),
    VentComponentDefinition(
        "AVD", "Avluftsdon", "terminal", "exhaust", ("AVL",), "Avleder avluft till det fria."
    ),
    VentComponentDefinition(
        "BS",
        "Brandspjäll",
        "damper",
        None,
        ("BSP", "BRANDSPJÄLL"),
        "Begränsar brand- och brandgasspridning.",
    ),
    VentComponentDefinition(
        "SS", "Spjäll", "damper", None, ("SPJ", "INJ"), "Reglerar eller stänger luftflöde."
    ),
    VentComponentDefinition("VAV", "VAV-spjäll", "damper", None, ("VRD",), "Variabelt luftflöde."),
    VentComponentDefinition("CAV", "CAV-spjäll", "damper", None, (), "Konstant luftflöde."),
    VentComponentDefinition(
        "LD", "Ljuddämpare", "silencer", None, ("LB", "LJUDDÄMPARE"), "Dämpar kanalburet ljud."
    ),
    VentComponentDefinition("FL", "Fläkt", "fan", None, ("FAN",), "Skapar lufttransport."),
    VentComponentDefinition(
        "AG",
        "Luftbehandlingsaggregat",
        "unit",
        None,
        ("AHU", "TA", "FA"),
        "Behandlar och transporterar luft.",
    ),
    VentComponentDefinition(
        "FI", "Filter", "filter", None, ("FILTER",), "Avskiljer partiklar ur luftströmmen."
    ),
    VentComponentDefinition("VB", "Värmebatteri", "coil", None, ("VVB",), "Värmer luft."),
    VentComponentDefinition("KB", "Kylbatteri", "coil", None, ("KKB",), "Kyler luft."),
    VentComponentDefinition(
        "TH", "Takhuv", "terminal", None, ("TAKHUV",), "Utelufts- eller avluftsanslutning på tak."
    ),
)


def component_registry() -> tuple[VentComponentDefinition, ...]:
    return _COMPONENTS


def normalise_symbol(value: str) -> str:
    upper = value.upper().strip()
    leading = re.match(r"([A-ZÅÄÖ]+)", upper)
    if leading:
        return leading.group(1)
    compact = re.sub(r"[^A-ZÅÄÖ0-9]", "", upper)
    return re.sub(r"\d+$", "", compact)


def resolve_component(value: str) -> VentComponentDefinition | None:
    symbol = normalise_symbol(value)
    for item in _COMPONENTS:
        if symbol == item.code or symbol in item.aliases:
            return item
    return None
