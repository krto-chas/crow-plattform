from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from typing import Any

_DIMENSION = re.compile(r"(?:Ø|D)?\s*(\d{2,4})(?:\s*[xX×]\s*(\d{2,4}))?")


def _technical_properties(item: dict[str, Any]) -> dict[str, Any]:
    evidence = item.get("evidence") or {}
    source = " ".join(
        str(v) for v in (item.get("source_value"), evidence.get("text"), evidence.get("label")) if v
    )
    match = _DIMENSION.search(source)
    dimension = None
    if match:
        dimension = f"{match.group(1)}x{match.group(2)}" if match.group(2) else f"Ø{match.group(1)}"
    length = (
        evidence.get("length")
        or evidence.get("length_m")
        or item.get("length")
        or item.get("length_m")
    )
    try:
        length_m = round(float(length), 3) if length is not None else None
    except (TypeError, ValueError):
        length_m = None
    return {"dimension": dimension, "length_m": length_m}


def build_quantity_takeoff(systems: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_category: dict[str, int] = defaultdict(int)
    total_length = 0.0
    measured_objects = 0
    unmeasured_objects = 0

    for system in systems:
        for component in system.get("components", []):
            properties = _technical_properties(component)
            component["technical_properties"] = properties
            code = component.get("component_code") or "UNCLASSIFIED"
            name = (
                component.get("component_name")
                or component.get("source_value")
                or "Okänd komponent"
            )
            dimension = properties["dimension"] or "Ej angiven"
            key = (code, name, dimension)
            if key not in groups:
                groups[key] = {
                    "component_code": code,
                    "component_name": name,
                    "category": component.get("category") or "unknown",
                    "dimension": dimension,
                    "quantity": 0,
                    "length_m": 0.0,
                    "system_ids": [],
                    "source_classification_ids": [],
                }
            row = groups[key]
            row["quantity"] += 1
            if system["vent_system_id"] not in row["system_ids"]:
                row["system_ids"].append(system["vent_system_id"])
            if component.get("classification_id"):
                row["source_classification_ids"].append(component["classification_id"])
            if properties["length_m"] is not None:
                row["length_m"] = round(row["length_m"] + properties["length_m"], 3)
                total_length += properties["length_m"]
                measured_objects += 1
            else:
                unmeasured_objects += 1
            by_category[row["category"]] += 1

    rows = sorted(
        groups.values(), key=lambda row: (row["category"], row["component_name"], row["dimension"])
    )
    for row in rows:
        if row["length_m"] == 0:
            row["length_m"] = None
    return {
        "schema_version": "crow-vent-quantity-v0.3",
        "line_count": len(rows),
        "total_component_count": sum(row["quantity"] for row in rows),
        "total_length_m": round(total_length, 3),
        "measured_object_count": measured_objects,
        "unmeasured_object_count": unmeasured_objects,
        "counts_by_category": dict(sorted(by_category.items())),
        "lines": rows,
    }


def quantity_takeoff_csv(takeoff: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        ["Komponentkod", "Komponent", "Kategori", "Dimension", "Antal", "Längd m", "System"]
    )
    for row in takeoff.get("lines", []):
        writer.writerow(
            [
                row["component_code"],
                row["component_name"],
                row["category"],
                row["dimension"],
                row["quantity"],
                "" if row["length_m"] is None else row["length_m"],
                ", ".join(row["system_ids"]),
            ]
        )
    return output.getvalue()
