from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
from math import hypot
from typing import Any

from .models import GeometryDocument, GeometryKind, GeometryObject
from .query import object_bounds
from .systems import identify_systems


def _center(item: GeometryObject) -> tuple[float, float] | None:
    bounds = object_bounds(item)
    if bounds is None:
        return None
    return ((bounds.min_x + bounds.max_x) / 2.0, (bounds.min_y + bounds.max_y) / 2.0)


def _distance(a: GeometryObject, b: GeometryObject) -> float | None:
    ca = _center(a)
    bounds = object_bounds(b)
    if ca is None or bounds is None:
        return None
    x, y = ca
    dx = max(bounds.min_x - x, 0.0, x - bounds.max_x)
    dy = max(bounds.min_y - y, 0.0, y - bounds.max_y)
    return hypot(dx, dy)


def _candidate_id(system_id: str, candidate_id: str, role: str) -> str:
    digest = sha256(f"{system_id}:{candidate_id}:{role}".encode()).hexdigest()[:16]
    return f"observation-{digest}"


def _confidence(distance: float, radius: float) -> float:
    if radius <= 0:
        return 0.0
    return round(max(0.0, min(1.0, 1.0 - distance / radius)), 4)


def discover_system_observations(
    document: GeometryDocument,
    *,
    tolerance: float = 0.001,
    association_radius: float = 100.0,
    layers: Iterable[str] | None = None,
    visible_only: bool = False,
) -> dict[str, Any]:
    """Associate domain-neutral label and component candidates with geometry systems.

    The result contains evidence candidates only. It deliberately avoids assigning
    ventilation, electrical, plumbing or other domain semantics.
    """
    if association_radius < 0:
        raise ValueError("association_radius must not be negative")

    systems_result = identify_systems(
        document,
        tolerance=tolerance,
        layers=layers,
        visible_only=visible_only,
    )
    objects = {item.object_id: item for item in document.objects}
    visible_layers = {layer.name.casefold() for layer in document.layers if layer.visible}

    candidates = [
        item
        for item in document.objects
        if item.kind in {GeometryKind.TEXT, GeometryKind.INSERT, GeometryKind.BLOCK}
        and (not visible_only or item.layer.casefold() in visible_layers)
    ]

    observations: list[dict[str, Any]] = []
    by_system: dict[str, list[str]] = {}
    assigned_candidates: set[str] = set()

    for system in systems_result["systems"]:
        system_id = str(system["system_id"])
        network_objects = [objects[oid] for oid in system["object_ids"] if oid in objects]
        system_observation_ids: list[str] = []
        for candidate in candidates:
            nearest_distance: float | None = None
            nearest_network_object: GeometryObject | None = None
            for network_object in network_objects:
                distance = _distance(candidate, network_object)
                if distance is None:
                    continue
                if nearest_distance is None or distance < nearest_distance:
                    nearest_distance = distance
                    nearest_network_object = network_object
            if (
                nearest_distance is None
                or nearest_distance > association_radius
                or nearest_network_object is None
            ):
                continue

            role = (
                "label_candidate" if candidate.kind is GeometryKind.TEXT else "component_candidate"
            )
            value = (
                str(candidate.properties.get("text") or "")
                if candidate.kind is GeometryKind.TEXT
                else str(candidate.properties.get("name") or "")
            )
            observation_id = _candidate_id(system_id, candidate.object_id, role)
            observations.append(
                {
                    "observation_id": observation_id,
                    "observation_type": role,
                    "system_id": system_id,
                    "candidate_object_id": candidate.object_id,
                    "candidate_kind": candidate.kind.value,
                    "candidate_layer": candidate.layer,
                    "candidate_value": value,
                    "nearest_network_object_id": nearest_network_object.object_id,
                    "distance": round(nearest_distance, 6),
                    "association_radius": association_radius,
                    "confidence": _confidence(nearest_distance, association_radius),
                    "domain_semantics": False,
                    "status": "candidate",
                }
            )
            system_observation_ids.append(observation_id)
            assigned_candidates.add(candidate.object_id)
        by_system[system_id] = system_observation_ids

    observations.sort(
        key=lambda item: (
            str(item["system_id"]),
            float(item["distance"]),
            str(item["candidate_object_id"]),
        )
    )
    unassigned = sorted(
        item.object_id for item in candidates if item.object_id not in assigned_candidates
    )
    return {
        "observation_version": "crow-geometry-observation-v1",
        "domain_semantics": False,
        "association_radius": association_radius,
        "system_count": systems_result["system_count"],
        "observation_count": len(observations),
        "candidate_object_count": len(candidates),
        "unassigned_candidate_object_ids": unassigned,
        "system_observation_ids": by_system,
        "observations": observations,
    }


def system_observations(
    document: GeometryDocument,
    system_id: str,
    *,
    tolerance: float = 0.001,
    association_radius: float = 100.0,
    layers: Iterable[str] | None = None,
    visible_only: bool = False,
) -> dict[str, Any]:
    result = discover_system_observations(
        document,
        tolerance=tolerance,
        association_radius=association_radius,
        layers=layers,
        visible_only=visible_only,
    )
    systems = identify_systems(
        document, tolerance=tolerance, layers=layers, visible_only=visible_only
    )
    if not any(str(system["system_id"]) == system_id for system in systems["systems"]):
        raise KeyError(system_id)
    items = [item for item in result["observations"] if item["system_id"] == system_id]
    return {
        "system_id": system_id,
        "observation_count": len(items),
        "observations": items,
        "domain_semantics": False,
    }
