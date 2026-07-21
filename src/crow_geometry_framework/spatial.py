from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from math import hypot
from typing import Any

from .models import BoundingBox2D, GeometryDocument, GeometryKind, GeometryObject
from .query import object_bounds


@dataclass(frozen=True)
class SpatialHit:
    object_id: str
    distance: float
    relation: str


def _center(bounds: BoundingBox2D) -> tuple[float, float]:
    return ((bounds.min_x + bounds.max_x) / 2.0, (bounds.min_y + bounds.max_y) / 2.0)


def _bbox_distance(bounds: BoundingBox2D, x: float, y: float) -> float:
    dx = max(bounds.min_x - x, 0.0, x - bounds.max_x)
    dy = max(bounds.min_y - y, 0.0, y - bounds.max_y)
    return hypot(dx, dy)


def intersects(a: BoundingBox2D, b: BoundingBox2D) -> bool:
    return not (a.max_x < b.min_x or a.min_x > b.max_x or a.max_y < b.min_y or a.min_y > b.max_y)


def objects_in_bbox(
    document: GeometryDocument,
    bbox: BoundingBox2D,
    *,
    kinds: Iterable[str] | None = None,
    layers: Iterable[str] | None = None,
    visible_only: bool = False,
    limit: int = 2000,
) -> list[GeometryObject]:
    kind_set = {str(value).casefold() for value in (kinds or [])}
    layer_set = {str(value).casefold() for value in (layers or [])}
    visible_layers = {layer.name.casefold() for layer in document.layers if layer.visible}
    result: list[GeometryObject] = []
    for item in document.objects:
        if kind_set and item.kind.value.casefold() not in kind_set:
            continue
        if layer_set and item.layer.casefold() not in layer_set:
            continue
        if visible_only and item.layer.casefold() not in visible_layers:
            continue
        bounds = object_bounds(item)
        if bounds is None or not intersects(bounds, bbox):
            continue
        result.append(item)
        if len(result) >= max(1, min(limit, 10000)):
            break
    return result


def nearest_objects(
    document: GeometryDocument,
    *,
    x: float,
    y: float,
    max_distance: float | None = None,
    kinds: Iterable[str] | None = None,
    layers: Iterable[str] | None = None,
    visible_only: bool = False,
    limit: int = 25,
    exclude_ids: Iterable[str] | None = None,
) -> list[tuple[GeometryObject, float]]:
    kind_set = {str(value).casefold() for value in (kinds or [])}
    layer_set = {str(value).casefold() for value in (layers or [])}
    excluded = set(exclude_ids or [])
    visible_layers = {layer.name.casefold() for layer in document.layers if layer.visible}
    candidates: list[tuple[GeometryObject, float]] = []
    for item in document.objects:
        if item.object_id in excluded:
            continue
        if kind_set and item.kind.value.casefold() not in kind_set:
            continue
        if layer_set and item.layer.casefold() not in layer_set:
            continue
        if visible_only and item.layer.casefold() not in visible_layers:
            continue
        bounds = object_bounds(item)
        if bounds is None:
            continue
        distance = _bbox_distance(bounds, x, y)
        if max_distance is not None and distance > max_distance:
            continue
        candidates.append((item, distance))
    candidates.sort(key=lambda pair: (pair[1], pair[0].object_id))
    return candidates[: max(1, min(limit, 1000))]


def related_objects(
    document: GeometryDocument,
    object_id: str,
    *,
    radius: float,
    limit: int = 50,
) -> dict[str, Any]:
    source = next((item for item in document.objects if item.object_id == object_id), None)
    if source is None:
        raise KeyError(object_id)
    bounds = object_bounds(source)
    if bounds is None:
        return {"source_object_id": object_id, "radius": radius, "items": []}
    x, y = _center(bounds)
    hits = nearest_objects(
        document,
        x=x,
        y=y,
        max_distance=radius,
        limit=limit,
        exclude_ids=[object_id],
    )
    items = []
    for item, distance in hits:
        relation = "nearby"
        other_bounds = object_bounds(item)
        if other_bounds and intersects(bounds, other_bounds):
            relation = "intersects"
        elif source.kind is GeometryKind.TEXT and item.kind is GeometryKind.INSERT:
            relation = "text-near-block"
        elif source.kind is GeometryKind.INSERT and item.kind is GeometryKind.TEXT:
            relation = "block-near-text"
        items.append(
            {
                "object_id": item.object_id,
                "kind": item.kind.value,
                "layer": item.layer,
                "distance": distance,
                "relation": relation,
                "properties": item.properties,
                "bounds": asdict(other_bounds) if other_bounds else None,
            }
        )
    return {
        "source_object_id": object_id,
        "radius": radius,
        "origin": {"x": x, "y": y},
        "items": items,
    }


def spatial_index_summary(document: GeometryDocument) -> dict[str, Any]:
    indexed = 0
    centers: list[tuple[float, float]] = []
    for item in document.objects:
        bounds = object_bounds(item)
        if bounds is None:
            continue
        indexed += 1
        centers.append(_center(bounds))
    return {
        "index_version": "crow-spatial-index-v1",
        "indexed_object_count": indexed,
        "unindexed_object_count": len(document.objects) - indexed,
        "document_bounds": asdict(document.bounds) if document.bounds else None,
        "center_extent": {
            "min_x": min((point[0] for point in centers), default=None),
            "min_y": min((point[1] for point in centers), default=None),
            "max_x": max((point[0] for point in centers), default=None),
            "max_y": max((point[1] for point in centers), default=None),
        },
    }
