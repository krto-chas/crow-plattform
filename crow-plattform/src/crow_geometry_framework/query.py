from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict
from math import hypot
from typing import Any

from .models import BoundingBox2D, GeometryDocument, GeometryKind, GeometryObject


def object_bounds(item: GeometryObject) -> BoundingBox2D | None:
    g = item.geometry
    if item.kind is GeometryKind.LINE:
        return BoundingBox2D(
            min(float(g["x1"]), float(g["x2"])),
            min(float(g["y1"]), float(g["y2"])),
            max(float(g["x1"]), float(g["x2"])),
            max(float(g["y1"]), float(g["y2"])),
        )
    if item.kind is GeometryKind.CIRCLE:
        cx, cy, r = float(g["cx"]), float(g["cy"]), abs(float(g["r"]))
        return BoundingBox2D(cx - r, cy - r, cx + r, cy + r)
    if item.kind is GeometryKind.ARC:
        cx, cy, r = float(g["cx"]), float(g["cy"]), abs(float(g["r"]))
        return BoundingBox2D(cx - r, cy - r, cx + r, cy + r)
    if item.kind in {
        GeometryKind.POLYLINE,
        GeometryKind.TEXT,
        GeometryKind.INSERT,
        GeometryKind.BLOCK,
    }:
        pts = g.get("points") or []
        if not pts and "x" in g and "y" in g:
            pts = [[g["x"], g["y"]]]
        xs = [float(p[0]) for p in pts if len(p) >= 2]
        ys = [float(p[1]) for p in pts if len(p) >= 2]
        if xs:
            return BoundingBox2D(min(xs), min(ys), max(xs), max(ys))
    return None


def object_measure(item: GeometryObject) -> dict[str, float]:
    g = item.geometry
    if item.kind is GeometryKind.LINE:
        return {"length": hypot(float(g["x2"]) - float(g["x1"]), float(g["y2"]) - float(g["y1"]))}
    if item.kind is GeometryKind.CIRCLE:
        r = abs(float(g["r"]))
        return {
            "radius": r,
            "diameter": 2 * r,
            "circumference": 2 * 3.141592653589793 * r,
            "area": 3.141592653589793 * r * r,
        }
    if item.kind is GeometryKind.POLYLINE:
        pts = g.get("points") or []
        length = sum(
            hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))
            for a, b in zip(pts, pts[1:], strict=False)
        )
        if g.get("closed") and len(pts) > 2:
            length += hypot(
                float(pts[0][0]) - float(pts[-1][0]), float(pts[0][1]) - float(pts[-1][1])
            )
        return {"length": length, "vertex_count": float(len(pts))}
    return {}


def search_geometry(
    document: GeometryDocument,
    *,
    text: str | None = None,
    kinds: Iterable[str] | None = None,
    layers: Iterable[str] | None = None,
    visible_only: bool = False,
    limit: int = 500,
) -> list[GeometryObject]:
    needle = (text or "").strip().casefold()
    kind_set = {str(k).casefold() for k in (kinds or [])}
    layer_set = {str(layer).casefold() for layer in (layers or [])}
    visible_layers = {layer.name.casefold() for layer in document.layers if layer.visible}
    result: list[GeometryObject] = []
    for item in document.objects:
        if kind_set and item.kind.value.casefold() not in kind_set:
            continue
        if layer_set and item.layer.casefold() not in layer_set:
            continue
        if visible_only and item.layer.casefold() not in visible_layers:
            continue
        if needle:
            haystack = " ".join(
                [
                    item.object_id,
                    item.kind.value,
                    item.layer,
                    str(item.properties.get("text", "")),
                    str(item.properties.get("name", "")),
                    str(item.properties.get("entity_type", "")),
                    str(item.source_locator),
                ]
            ).casefold()
            if needle not in haystack:
                continue
        result.append(item)
        if len(result) >= max(1, min(limit, 5000)):
            break
    return result


def geometry_index(document: GeometryDocument) -> dict[str, Any]:
    kind_counts: dict[str, int] = {}
    texts: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    for item in document.objects:
        kind_counts[item.kind.value] = kind_counts.get(item.kind.value, 0) + 1
        if item.kind is GeometryKind.TEXT:
            texts.append(
                {
                    "object_id": item.object_id,
                    "text": item.properties.get("text", ""),
                    "layer": item.layer,
                }
            )
        elif item.kind is GeometryKind.INSERT:
            blocks.append(
                {
                    "object_id": item.object_id,
                    "name": item.properties.get("name", ""),
                    "layer": item.layer,
                }
            )
    return {
        "object_count": len(document.objects),
        "layer_count": len(document.layers),
        "kind_counts": dict(sorted(kind_counts.items())),
        "texts": texts,
        "blocks": blocks,
    }


def object_payload(item: GeometryObject) -> dict[str, Any]:
    payload = asdict(item)
    bounds = object_bounds(item)
    payload["bounds"] = asdict(bounds) if bounds else None
    payload["measurements"] = object_measure(item)
    return payload
