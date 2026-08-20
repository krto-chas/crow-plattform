"""Positionstaxonomi 1.1–4.6 (Handlingar/Föroreningar/Funktioner/Klimat).

Lexikonet är installationsdata: kundutbytbar JSON laddad via
importlib.resources, samma mönster som defekttyperna.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources


@dataclass(frozen=True, slots=True)
class ProtocolPosition:
    position_id: str
    label: str
    group_id: str
    group_label: str


@lru_cache(maxsize=1)
def _load() -> tuple[tuple[ProtocolPosition, ...], dict[str, str]]:
    resource = resources.files("crow_ovk_field").joinpath("protocol_positions.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    positions: list[ProtocolPosition] = []
    for group in payload.get("groups", []):
        for item in group.get("positions", []):
            positions.append(
                ProtocolPosition(
                    position_id=str(item["id"]),
                    label=str(item["label"]),
                    group_id=str(group["id"]),
                    group_label=str(group["label"]),
                )
            )
    defaults = {str(key): str(value) for key, value in payload.get("defect_defaults", {}).items()}
    return tuple(positions), defaults


def load_positions() -> tuple[ProtocolPosition, ...]:
    return _load()[0]


def position_by_id(position_id: str) -> ProtocolPosition:
    for position in load_positions():
        if position.position_id == position_id:
            return position
    raise KeyError(f"unknown protocol position {position_id!r}")


def default_position_for(defect_type: str) -> ProtocolPosition | None:
    defaults = _load()[1]
    position_id = defaults.get(defect_type)
    return position_by_id(position_id) if position_id else None
