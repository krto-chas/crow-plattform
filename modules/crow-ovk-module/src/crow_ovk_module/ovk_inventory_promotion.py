"""Additive inventory promotion from a synced field inspection.

Only structural identities and stated design values cross the boundary.
No inspection outcome, evidence or history is copied to the register.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from hashlib import sha256
from typing import Any

from .ovk_trapphus import display_number, split_display_number, trapphus_names


def inventory_revision(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def plan_inventory_promotion(
    inventory: dict[str, Any],
    snapshot: dict[str, Any],
    assignments: dict[str, str],
) -> dict[str, Any]:
    result = deepcopy(inventory)
    additions: list[dict[str, str]] = []
    conflicts: list[str] = []
    unresolved: list[dict[str, str]] = []
    systems = {row["system_id"] for row in inventory["systems"]}
    units = {row["unit_id"]: row for row in result["units"]}
    rooms = {
        room["room_id"]: (unit["unit_id"], room)
        for unit in result["units"]
        for room in unit["rooms"]
    }
    points = {
        point["point_id"]: (room["room_id"], point)
        for unit in result["units"]
        for room in unit["rooms"]
        for point in room.get("measurement_points", [])
    }

    def normalized(value: str) -> str:
        return " ".join(value.split()).casefold()

    # Fältet bär visade nummer ("54-1101") för enheter i trapphus; registret
    # lagrar numret i trapphuset och en hänvisning.
    names = trapphus_names(inventory)

    def safe_id(value: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_-]+", value))

    def add(kind: str, identity: str, label: str) -> None:
        additions.append({"kind": kind, "id": identity, "label": label})

    field_units = snapshot.get("units", [])
    field_rooms = snapshot.get("rooms", [])
    field_points = snapshot.get("measurements", [])
    numbers: dict[str, int] = {}
    for row in field_units:
        number = normalized(row["number"])
        numbers[number] = numbers.get(number, 0) + 1
    for point in field_points:
        if not any(
            room["room_id"] == point.get("room_id") and room["unit_id"] == point["unit_id"]
            for room in field_rooms
        ):
            conflicts.append(f"Don {point['point_label']}: säker rumskoppling saknas.")
    for source in field_units:
        unit_id = source["unit_id"]
        number = source["number"].strip()
        kind = source["kind"]
        label = number
        if not safe_id(unit_id) or not number or numbers[normalized(number)] != 1:
            conflicts.append(f"Enhet {label}: ogiltigt ID eller tvetydigt nummer.")
            continue
        if any(
            other["unit_id"] != unit_id
            and normalized(display_number(other, names)) == normalized(number)
            for other in units.values()
        ):
            conflicts.append(f"Enhet {label}: numret finns med annat ID.")
            continue
        unit = units.get(unit_id)
        if unit is not None:
            # En besiktning som skapades innan enheten fick sitt trapphus bär
            # numret utan trapphusnamn; identiteten är enhetens ID.
            if number not in {display_number(unit, names), unit["number"]} or unit["kind"] != kind:
                conflicts.append(f"Enhet {label}: befintligt ID har annan beteckning eller typ.")
                continue
        else:
            trapphus_id, local_number = split_display_number(number, names)
            unit = {"unit_id": unit_id, "number": local_number, "kind": kind, "rooms": []}
            if trapphus_id is not None:
                unit["trapphus_id"] = trapphus_id
            result["units"].append(unit)
            units[unit_id] = unit
            add("unit", unit_id, label)
        # BOM is not evidence of the interior. Keep the number, but do not
        # promote room/point proposals from a unit marked inaccessible.
        if source.get("status") == "bom":
            conflicts.append(f"Enhet {label}: BOM, rum och don förs inte över.")
            continue
        for field_room in field_rooms:
            if field_room["unit_id"] != unit_id:
                continue
            room_id = field_room["room_id"]
            name = field_room["name"].strip()
            room_label = f"{label} / {name}"
            if not safe_id(room_id) or not name:
                conflicts.append(f"{room_label}: ogiltigt rums-ID eller namn.")
                continue
            known_room = rooms.get(room_id)
            if known_room is not None:
                owner, room = known_room
                if owner != unit_id or room["name"] != name:
                    conflicts.append(f"{room_label}: rums-ID har annan koppling eller benämning.")
                    continue
            else:
                if any(normalized(r["name"]) == normalized(name) for r in unit["rooms"]):
                    conflicts.append(f"{room_label}: rumsnamnet finns med annat ID.")
                    continue
                room = {"room_id": room_id, "name": name}
                unit["rooms"].append(room)
                rooms[room_id] = (unit_id, room)
                add("room", room_id, room_label)
            for field_point in field_points:
                if field_point["unit_id"] != unit_id or field_point.get("room_id") != room_id:
                    continue
                point_id = field_point["measurement_id"]
                point_label = field_point["point_label"].strip()
                full_label = f"{room_label} / {point_label}"
                if not safe_id(point_id) or not point_label:
                    conflicts.append(f"{full_label}: ogiltigt don-ID eller namn.")
                    continue
                system = assignments.get(point_id, field_point.get("system_id"))
                design = field_point.get("designed_value")
                if design is not None and not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", design):
                    conflicts.append(f"{full_label}: ogiltigt projekterat flöde.")
                    continue
                candidate = {
                    "point_id": point_id,
                    "label": point_label,
                    "point_type": field_point["point_type"],
                    "system_id": system,
                    "designed_value": design,
                    "unit_of_measure": field_point["unit_of_measure"],
                }
                known_point = points.get(point_id)
                if known_point is not None:
                    if known_point != (room_id, candidate):
                        conflicts.append(
                            f"{full_label}: befintligt don avviker, lämnas oförändrat."
                        )
                    continue
                if any(
                    normalized(p["label"]) == normalized(point_label)
                    and p["point_type"] == candidate["point_type"]
                    for p in room.get("measurement_points", [])
                ):
                    conflicts.append(f"{full_label}: liknande don finns med annat ID.")
                    continue
                if system not in systems:
                    unresolved.append({"point_id": point_id, "label": full_label})
                    continue
                room.setdefault("measurement_points", []).append(candidate)
                points[point_id] = (room_id, candidate)
                flow = f"{design} l/s" if design is not None else "projekterat värde saknas"
                add("point", point_id, f"{full_label} / {system} / {flow}")
    return {
        "structure": result,
        "additions": additions,
        "conflicts": conflicts,
        "unresolved": unresolved,
    }
