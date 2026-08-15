from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from hashlib import sha256
from typing import Any

from .models import GeometryDocument
from .topology import build_topology
from .tracing import segment_network


def identify_systems(
    document: GeometryDocument,
    *,
    tolerance: float = 0.001,
    layers: Iterable[str] | None = None,
    visible_only: bool = False,
) -> dict[str, Any]:
    """Identify connected geometry systems and classify their segments.

    This layer is deliberately domain-neutral. It describes connectivity and
    branch structure, but does not infer ventilation, electrical or plumbing
    semantics.
    """
    graph = build_topology(document, tolerance=tolerance, layers=layers, visible_only=visible_only)
    segmented = segment_network(
        document, tolerance=tolerance, layers=layers, visible_only=visible_only
    )
    nodes = {node["node_id"]: node for node in graph["nodes"]}

    node_component: dict[str, int] = {}
    for idx, component in enumerate(graph["components"], 1):
        for node_id in component["node_ids"]:
            node_component[node_id] = idx

    component_edges: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for edge in graph["edges"]:
        component_edges[node_component[edge["start_node_id"]]].append(edge)

    component_segments: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for segment in segmented["segments"]:
        node_ids = segment.get("node_ids") or []
        if node_ids:
            component_segments[node_component[node_ids[0]]].append(segment)

    systems: list[dict[str, Any]] = []
    object_membership: dict[str, dict[str, str]] = {}
    for idx, component in enumerate(graph["components"], 1):
        node_ids = list(component["node_ids"])
        comp_edges = component_edges[idx]
        comp_segments = component_segments[idx]
        junctions = [nid for nid in node_ids if nodes[nid]["degree"] > 2]
        dangling = [nid for nid in node_ids if nodes[nid]["degree"] == 1]
        total_length = round(sum(float(edge["length"]) for edge in comp_edges), 6)
        layers_used = sorted({str(edge["layer"]) for edge in comp_edges})
        object_ids = sorted({str(edge["object_id"]) for edge in comp_edges})
        cycle_rank = max(0, len(comp_edges) - len(node_ids) + 1)
        signature = "|".join(object_ids) or "|".join(node_ids)
        system_id = f"system-{sha256(signature.encode('utf-8')).hexdigest()[:12]}"

        classified_segments: list[dict[str, Any]] = []
        for segment in comp_segments:
            boundary_ids = [nid for nid in segment.get("node_ids", []) if nodes[nid]["degree"] != 2]
            junction_touches = sum(1 for nid in boundary_ids if nodes[nid]["degree"] > 2)
            dangling_touches = sum(1 for nid in boundary_ids if nodes[nid]["degree"] == 1)
            if segment.get("closed"):
                role = "loop"
            elif junction_touches >= 2:
                role = "trunk"
            elif junction_touches == 1 and dangling_touches >= 1:
                role = "terminal_branch"
            elif junction_touches == 1:
                role = "branch"
            elif dangling_touches >= 2:
                role = "run"
            else:
                role = "isolated"
            item = dict(segment)
            item["role"] = role
            classified_segments.append(item)
            for object_id in segment.get("object_ids", []):
                object_membership[str(object_id)] = {
                    "system_id": system_id,
                    "segment_id": str(segment["segment_id"]),
                    "role": role,
                }

        if cycle_rank > 0:
            network_class = "looped"
        elif junctions:
            network_class = "branched"
        elif len(comp_edges) == 1:
            network_class = "single"
        else:
            network_class = "linear"

        systems.append(
            {
                "system_id": system_id,
                "network_class": network_class,
                "node_count": len(node_ids),
                "edge_count": len(comp_edges),
                "object_count": len(object_ids),
                "segment_count": len(classified_segments),
                "junction_count": len(junctions),
                "dangling_end_count": len(dangling),
                "cycle_rank": cycle_rank,
                "total_length": total_length,
                "layers": layers_used,
                "object_ids": object_ids,
                "segments": classified_segments,
            }
        )

    return {
        "system_identification_version": "crow-system-graph-v1",
        "domain_semantics": False,
        "tolerance": tolerance,
        "system_count": len(systems),
        "total_length": round(sum(float(item["total_length"]) for item in systems), 6),
        "systems": systems,
        "object_membership": object_membership,
    }


def object_system(
    document: GeometryDocument,
    object_id: str,
    *,
    tolerance: float = 0.001,
    layers: Iterable[str] | None = None,
    visible_only: bool = False,
) -> dict[str, Any]:
    result = identify_systems(
        document, tolerance=tolerance, layers=layers, visible_only=visible_only
    )
    membership = result["object_membership"].get(object_id)
    exists = any(item.object_id == object_id for item in document.objects)
    if not exists:
        raise KeyError(object_id)
    if membership is None:
        return {"object_id": object_id, "connected_system": False, "system": None}
    system = next(
        item for item in result["systems"] if item["system_id"] == membership["system_id"]
    )
    return {
        "object_id": object_id,
        "connected_system": True,
        "membership": membership,
        "system": system,
    }
