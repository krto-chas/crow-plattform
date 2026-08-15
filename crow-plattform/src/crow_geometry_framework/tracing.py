from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from typing import Any

from .models import GeometryDocument
from .topology import build_topology


def trace_network(
    document: GeometryDocument,
    start_object_id: str,
    *,
    tolerance: float = 0.001,
    layers: Iterable[str] | None = None,
    visible_only: bool = False,
    max_depth: int | None = None,
    stop_at_junctions: bool = False,
) -> dict[str, Any]:
    """Trace connected geometry from a source object through the topology graph.

    Traversal is object-oriented while the underlying graph remains node/edge based.
    ``max_depth`` counts object-to-object hops. When ``stop_at_junctions`` is enabled,
    traversal includes the objects touching a junction but does not continue beyond it.
    """
    graph = build_topology(
        document,
        tolerance=tolerance,
        layers=layers,
        visible_only=visible_only,
    )
    object_lookup = {item.object_id: item for item in document.objects}
    if start_object_id not in object_lookup:
        raise KeyError(start_object_id)

    node_by_id = {node["node_id"]: node for node in graph["nodes"]}
    object_nodes: dict[str, set[str]] = {}
    for node in graph["nodes"]:
        for object_id in node["object_ids"]:
            object_nodes.setdefault(object_id, set()).add(node["node_id"])

    if start_object_id not in object_nodes:
        return {
            "trace_version": "crow-network-trace-v1",
            "source_object_id": start_object_id,
            "tolerance": tolerance,
            "object_count": 1,
            "node_count": 0,
            "edge_count": 0,
            "max_depth_reached": 0,
            "terminated_at_junctions": [],
            "objects": [
                {
                    "object_id": start_object_id,
                    "kind": object_lookup[start_object_id].kind.value,
                    "layer": object_lookup[start_object_id].layer,
                    "depth": 0,
                }
            ],
            "node_ids": [],
            "edge_ids": [],
        }

    queue: deque[tuple[str, int]] = deque([(start_object_id, 0)])
    visited_objects: dict[str, int] = {}
    visited_nodes: set[str] = set()
    terminated: set[str] = set()

    while queue:
        object_id, depth = queue.popleft()
        if object_id in visited_objects and visited_objects[object_id] <= depth:
            continue
        visited_objects[object_id] = depth
        if max_depth is not None and depth >= max_depth:
            visited_nodes.update(object_nodes.get(object_id, set()))
            continue

        for node_id in sorted(object_nodes.get(object_id, set())):
            visited_nodes.add(node_id)
            node = node_by_id[node_id]
            if stop_at_junctions and int(node["degree"]) > 2 and depth > 0:
                terminated.add(node_id)
                continue
            for adjacent_object_id in sorted(node["object_ids"]):
                if adjacent_object_id != object_id:
                    queue.append((adjacent_object_id, depth + 1))

    edge_ids = [edge["edge_id"] for edge in graph["edges"] if edge["object_id"] in visited_objects]
    ordered = sorted(visited_objects.items(), key=lambda item: (item[1], item[0]))
    return {
        "trace_version": "crow-network-trace-v1",
        "source_object_id": start_object_id,
        "tolerance": tolerance,
        "object_count": len(visited_objects),
        "node_count": len(visited_nodes),
        "edge_count": len(edge_ids),
        "max_depth_reached": max(visited_objects.values(), default=0),
        "terminated_at_junctions": sorted(terminated),
        "objects": [
            {
                "object_id": object_id,
                "kind": object_lookup[object_id].kind.value,
                "layer": object_lookup[object_id].layer,
                "depth": depth,
            }
            for object_id, depth in ordered
        ],
        "node_ids": sorted(visited_nodes),
        "edge_ids": sorted(edge_ids),
    }


def segment_network(
    document: GeometryDocument,
    *,
    tolerance: float = 0.001,
    layers: Iterable[str] | None = None,
    visible_only: bool = False,
) -> dict[str, Any]:
    """Split topology into branch-to-branch or end-to-branch segments."""
    graph = build_topology(
        document,
        tolerance=tolerance,
        layers=layers,
        visible_only=visible_only,
    )
    nodes = {node["node_id"]: node for node in graph["nodes"]}
    adjacency: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in nodes}
    for edge in graph["edges"]:
        adjacency[edge["start_node_id"]].append(edge)
        adjacency[edge["end_node_id"]].append(edge)

    boundary_nodes = {node_id for node_id, node in nodes.items() if int(node["degree"]) != 2}
    used_edges: set[str] = set()
    segments: list[dict[str, Any]] = []

    def other_node(edge: dict[str, Any], node_id: str) -> str:
        return str(
            edge["end_node_id"] if edge["start_node_id"] == node_id else edge["start_node_id"]
        )

    for start_node in sorted(boundary_nodes):
        for first_edge in sorted(adjacency[start_node], key=lambda item: str(item["edge_id"])):
            if first_edge["edge_id"] in used_edges:
                continue
            node_path = [start_node]
            edge_path: list[str] = []
            object_ids: list[str] = []
            length = 0.0
            current_node = start_node
            current_edge = first_edge

            while True:
                edge_id = str(current_edge["edge_id"])
                if edge_id in used_edges:
                    break
                used_edges.add(edge_id)
                edge_path.append(edge_id)
                object_ids.append(str(current_edge["object_id"]))
                length += float(current_edge["length"])
                next_node = other_node(current_edge, current_node)
                node_path.append(next_node)
                if next_node in boundary_nodes:
                    break
                candidates = [
                    edge for edge in adjacency[next_node] if edge["edge_id"] not in used_edges
                ]
                if not candidates:
                    break
                current_node = next_node
                current_edge = sorted(candidates, key=lambda item: str(item["edge_id"]))[0]

            segments.append(
                {
                    "segment_id": f"segment-{len(segments) + 1:05d}",
                    "start_node_id": node_path[0],
                    "end_node_id": node_path[-1],
                    "node_ids": node_path,
                    "edge_ids": edge_path,
                    "object_ids": list(dict.fromkeys(object_ids)),
                    "length": length,
                }
            )

    # Closed loops contain no boundary nodes. Preserve each loop as one segment.
    for edge in graph["edges"]:
        if edge["edge_id"] in used_edges:
            continue
        start_node = str(edge["start_node_id"])
        current_node = start_node
        current_edge = edge
        node_path = [start_node]
        edge_path = []
        object_ids = []
        length = 0.0
        while True:
            edge_id = str(current_edge["edge_id"])
            if edge_id in used_edges:
                break
            used_edges.add(edge_id)
            edge_path.append(edge_id)
            object_ids.append(str(current_edge["object_id"]))
            length += float(current_edge["length"])
            next_node = other_node(current_edge, current_node)
            node_path.append(next_node)
            candidates = [
                candidate
                for candidate in adjacency[next_node]
                if candidate["edge_id"] not in used_edges
            ]
            if not candidates:
                break
            current_node = next_node
            current_edge = sorted(candidates, key=lambda item: str(item["edge_id"]))[0]
        segments.append(
            {
                "segment_id": f"segment-{len(segments) + 1:05d}",
                "start_node_id": node_path[0],
                "end_node_id": node_path[-1],
                "node_ids": node_path,
                "edge_ids": edge_path,
                "object_ids": list(dict.fromkeys(object_ids)),
                "length": length,
                "closed": node_path[0] == node_path[-1],
            }
        )

    return {
        "segmentation_version": "crow-network-segmentation-v1",
        "tolerance": tolerance,
        "segment_count": len(segments),
        "boundary_node_count": len(boundary_nodes),
        "segments": segments,
    }
