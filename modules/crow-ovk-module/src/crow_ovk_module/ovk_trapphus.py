"""Trapphus (portar) och enhetens visade nummer.

Registret lagrar lägenhetsnumret som det står i trapphuset ("1101") och en
hänvisning till trapphuset. I fält bär enheten portens namn som egen uppgift.
Utåt, i protokoll och listor, skrivs numret med porten framför ("54-1101"),
så att samma nummer i två portar går att skilja åt.
"""

from __future__ import annotations

from typing import Any


def normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def trapphus_names(structure: dict[str, Any] | None) -> dict[str, str]:
    """Trapphusens namn per id. En struktur utan trapphus ger en tom tabell."""

    result: dict[str, str] = {}
    rows = (structure or {}).get("trapphus", [])
    if not isinstance(rows, list):
        return result
    for row in rows:
        if isinstance(row, dict):
            identity, namn = row.get("trapphus_id"), row.get("namn")
            if isinstance(identity, str) and isinstance(namn, str) and namn.strip():
                result[identity] = " ".join(namn.split())
    return result


def display_number(unit: dict[str, Any], names: dict[str, str]) -> str:
    """Numret som det visas utåt: "54-1101" i trapphus 54, annars "1101"."""

    number = str(unit.get("number", "")).strip()
    namn = names.get(unit.get("trapphus_id") or "")
    return f"{namn}-{number}" if namn else number
