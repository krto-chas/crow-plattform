from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from math import hypot
from typing import Any

from .models import GeometryDocument, GeometryKind, GeometryObject


@dataclass(frozen=True)
class TopologyNode:
    node_id: str
    x: float
    y: float
    object_ids: tuple[str, ...]


@dataclass(frozen=True)
class TopologyEdge:
    edge_id: str
    object_id: str
    start_node_id: str
    end_node_id: str
    length: float
    layer: str


def _point_key(x: float, y: float, tolerance: float) -> tuple[int, int]:
    scale = 1.0 / max(tolerance, 1e-12)
    return (round(x * scale), round(y * scale))


def _segments(item: GeometryObject) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    g = item.geometry
    if item.kind is GeometryKind.LINE:
        return [((float(g["x1"]), float(g["y1"])), (float(g["x2"]), float(g["y2"])))]
    if item.kind is GeometryKind.POLYLINE:
        points = [(float(p[0]), float(p[1])) for p in g.get("points", []) if len(p) >= 2]
        result = list(zip(points, points[1:], strict=False))
        if g.get("closed") and len(points) > 2:
            result.append((points[-1], points[0]))
        return result
    return []


def build_topology(
    document: GeometryDocument,
    *,
    tolerance: float = 0.001,
    layers: Iterable[str] | None = None,
    visible_only: bool = False,
) -> dict[str, Any]:
    layer_filter = {str(v).casefold() for v in (layers or [])}
    visible = {layer.name.casefold() for layer in document.layers if layer.visible}
    node_points: dict[tuple[int, int], tuple[float, float]] = {}
    node_objects: dict[tuple[int, int], set[str]] = {}
    raw_edges: list[tuple[GeometryObject, tuple[float, float], tuple[float, float]]] = []

    for item in document.objects:
        if layer_filter and item.layer.casefold() not in layer_filter:
            continue
        if visible_only and item.layer.casefold() not in visible:
            continue
        for start, end in _segments(item):
            raw_edges.append((item, start, end))
            for point in (start, end):
                key = _point_key(point[0], point[1], tolerance)
                node_points.setdefault(key, point)
                node_objects.setdefault(key, set()).add(item.object_id)

    key_to_id = {key: f"node-{idx:06d}" for idx, key in enumerate(sorted(node_points), 1)}
    nodes = [
        TopologyNode(
            key_to_id[key],
            node_points[key][0],
            node_points[key][1],
            tuple(sorted(node_objects[key])),
        )
        for key in sorted(node_points)
    ]
    edges: list[TopologyEdge] = []
    for idx, (item, start, end) in enumerate(raw_edges, 1):
        a = key_to_id[_point_key(start[0], start[1], tolerance)]
        b = key_to_id[_point_key(end[0], end[1], tolerance)]
        edges.append(
            TopologyEdge(
                edge_id=f"edge-{idx:06d}",
                object_id=item.object_id,
                start_node_id=a,
                end_node_id=b,
                length=hypot(end[0] - start[0], end[1] - start[1]),
                layer=item.layer,
            )
        )

    degree: dict[str, int] = {node.node_id: 0 for node in nodes}
    adjacency: dict[str, set[str]] = {node.node_id: set() for node in nodes}
    for edge in edges:
        degree[edge.start_node_id] += 1
        degree[edge.end_node_id] += 1
        adjacency[edge.start_node_id].add(edge.end_node_id)
        adjacency[edge.end_node_id].add(edge.start_node_id)

    visited: set[str] = set()
    components: list[list[str]] = []
    for node in nodes:
        if node.node_id in visited:
            continue
        stack = [node.node_id]
        component: list[str] = []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            stack.extend(sorted(adjacency[current] - visited, reverse=True))
        components.append(sorted(component))

    return {
        "topology_version": "crow-topology-v1",
        "tolerance": tolerance,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "component_count": len(components),
        "dangling_node_count": sum(1 for value in degree.values() if value == 1),
        "junction_node_count": sum(1 for value in degree.values() if value > 2),
        "nodes": [dict(asdict(node), degree=degree[node.node_id]) for node in nodes],
        "edges": [asdict(edge) for edge in edges],
        "components": [
            {"component_id": f"component-{idx:04d}", "node_ids": item, "node_count": len(item)}
            for idx, item in enumerate(components, 1)
        ],
    }


def connected_objects(
    document: GeometryDocument, object_id: str, *, tolerance: float = 0.001
) -> dict[str, Any]:
    graph = build_topology(document, tolerance=tolerance)
    node_ids = {node["node_id"] for node in graph["nodes"] if object_id in node["object_ids"]}
    if not node_ids and not any(item.object_id == object_id for item in document.objects):
        raise KeyError(object_id)
    connected_ids: set[str] = set()
    for node in graph["nodes"]:
        if node["node_id"] in node_ids:
            connected_ids.update(node["object_ids"])
    connected_ids.discard(object_id)
    lookup = {item.object_id: item for item in document.objects}
    return {
        "source_object_id": object_id,
        "tolerance": tolerance,
        "connection_node_ids": sorted(node_ids),
        "items": [
            {"object_id": oid, "kind": lookup[oid].kind.value, "layer": lookup[oid].layer}
            for oid in sorted(connected_ids)
            if oid in lookup
        ],
    }
