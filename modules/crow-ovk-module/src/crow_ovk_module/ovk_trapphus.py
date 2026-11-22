"""Trapphus och enhetens visade nummer.

Registret lagrar lägenhetsnumret som det står i trapphuset ("1101") och en
hänvisning till trapphuset. Utåt, i besiktningens frysta struktur och därmed i
fältappen och protokollet, visas numret med trapphusets namn framför
("54-1101"), så att samma nummer i två trapphus går att skilja åt.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def trapphus_names(structure: dict[str, Any]) -> dict[str, str]:
    """Trapphusens namn per id. En struktur utan trapphus ger en tom tabell."""

    result: dict[str, str] = {}
    rows = structure.get("trapphus", [])
    if not isinstance(rows, list):
        return result
    for row in rows:
        if isinstance(row, dict):
            identity, namn = row.get("trapphus_id"), row.get("namn")
            if isinstance(identity, str) and isinstance(namn, str) and namn.strip():
                result[identity] = namn.strip()
    return result


def display_number(unit: dict[str, Any], names: dict[str, str]) -> str:
    """Numret som det visas utåt: "54-1101" i trapphus 54, annars "1101"."""

    number = str(unit.get("number", "")).strip()
    namn = names.get(unit.get("trapphus_id") or "")
    return f"{namn}-{number}" if namn else number


def split_display_number(number: str, names: dict[str, str]) -> tuple[str | None, str]:
    """Tolka ett visat nummer tillbaka till trapphus och nummer i trapphuset.

    Längsta matchande trapphusnamn vinner. Utan träff hör numret inte till
    något trapphus och lämnas som det är.
    """

    text = number.strip()
    best: tuple[str | None, str] = (None, text)
    best_length = -1
    for identity, namn in names.items():
        head, separator, tail = (
            text[: len(namn)],
            text[len(namn) : len(namn) + 1],
            text[len(namn) + 1 :],
        )
        if head.casefold() == namn.casefold() and separator == "-" and tail.strip():
            if len(namn) > best_length:
                best, best_length = (identity, tail.strip()), len(namn)
    return best


def structure_for_inspection(structure: dict[str, Any]) -> dict[str, Any]:
    """Strukturen som fryses i besiktningen, med visade nummer på enheterna.

    Trapphuslistan och enheternas hänvisning följer med, så att numret går att
    tolka tillbaka. En struktur utan trapphus lämnas oförändrad.
    """

    names = trapphus_names(structure)
    if not names:
        return structure
    result = deepcopy(structure)
    for unit in result.get("units", []):
        if isinstance(unit, dict) and unit.get("trapphus_id") in names:
            unit["number"] = display_number(unit, names)
    return result
