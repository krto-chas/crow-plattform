from __future__ import annotations

from collections import Counter, deque
from typing import Any

from .service import BuildingGraphService


class GraphIntegrityService:
    """Samlad RC1-validering och traversal för hela Building Graph."""

    def __init__(self, graph: BuildingGraphService):
        self.graph = graph

    def validate(self) -> dict[str, Any]:
        data = self.graph.repository.load()
        objects = {item["id"]: item for item in data["objects"]}
        evidence = {item["id"] for item in data["evidence"]}
        issues: list[dict[str, Any]] = []

        def add(code: str, severity: str, entity_id: str, message: str) -> None:
            issues.append(
                {"code": code, "severity": severity, "entity_id": entity_id, "message": message}
            )

        for relation in data["relations"]:
            if relation["source_id"] not in objects:
                add(
                    "relation_source_missing",
                    "error",
                    relation["id"],
                    "Relationens källobjekt saknas",
                )
            if relation["target_id"] not in objects:
                add(
                    "relation_target_missing",
                    "error",
                    relation["id"],
                    "Relationens målobjekt saknas",
                )
            for evidence_id in relation.get("evidence_ids", []):
                if evidence_id not in evidence:
                    add(
                        "evidence_missing",
                        "error",
                        relation["id"],
                        f"Evidens saknas: {evidence_id}",
                    )

        for obj in data["objects"]:
            for evidence_id in obj.get("evidence_ids", []):
                if evidence_id not in evidence:
                    add("evidence_missing", "error", obj["id"], f"Evidens saknas: {evidence_id}")

        for prop in data["properties"]:
            if prop["owner_id"] not in objects:
                add("property_owner_missing", "error", prop["id"], "Egenskapens ägare saknas")
            for evidence_id in prop.get("evidence_ids", []):
                if evidence_id not in evidence:
                    add("evidence_missing", "error", prop["id"], f"Evidens saknas: {evidence_id}")

        # En teknisk komponent ska vara kopplad till exakt ett system i RC1.
        belongs = Counter(
            relation["source_id"]
            for relation in data["relations"]
            if relation.get("relation_type") == "belongs_to"
            and objects.get(relation.get("target_id"), {}).get("object_type") == "technical_system"
        )
        for obj in data["objects"]:
            if obj.get("object_type") == "technical_component" and belongs[obj["id"]] == 0:
                add(
                    "component_without_system",
                    "warning",
                    obj["id"],
                    "Teknisk komponent saknar systemkoppling",
                )
            if obj.get("object_type") == "technical_component" and belongs[obj["id"]] > 1:
                add(
                    "component_multiple_systems",
                    "warning",
                    obj["id"],
                    "Teknisk komponent tillhör flera system",
                )

        errors = sum(1 for issue in issues if issue["severity"] == "error")
        warnings = sum(1 for issue in issues if issue["severity"] == "warning")
        return {
            "schema": "crow-building-graph-1.0-rc1",
            "valid": errors == 0,
            "issues": issues,
            "summary": {
                "objects": len(data["objects"]),
                "relations": len(data["relations"]),
                "properties": len(data["properties"]),
                "evidence": len(data["evidence"]),
                "history": len(data["history"]),
                "errors": errors,
                "warnings": warnings,
            },
        }

    def traverse(
        self, start_id: str, *, relation_types: set[str] | None = None, max_depth: int = 10
    ) -> dict[str, Any]:
        if self.graph.repository.get("objects", start_id) is None:
            raise KeyError(start_id)
        if not 1 <= max_depth <= 100:
            raise ValueError("max_depth måste ligga mellan 1 och 100")
        data = self.graph.repository.load()
        object_by_id = {item["id"]: item for item in data["objects"]}
        outgoing: dict[str, list[dict[str, Any]]] = {}
        for relation in data["relations"]:
            if relation_types is None or relation.get("relation_type") in relation_types:
                outgoing.setdefault(relation["source_id"], []).append(relation)
        visited = {start_id}
        queue = deque([(start_id, 0)])
        traversed: list[dict[str, Any]] = []
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for relation in outgoing.get(current, []):
                traversed.append(relation)
                target = relation["target_id"]
                if target not in visited:
                    visited.add(target)
                    queue.append((target, depth + 1))
        return {
            "start_id": start_id,
            "objects": [object_by_id[item] for item in visited if item in object_by_id],
            "relations": traversed,
            "summary": {"reached_objects": max(0, len(visited) - 1), "relations": len(traversed)},
        }

    def export_snapshot(self) -> dict[str, Any]:
        data = self.graph.repository.load()
        return {
            "schema": "crow-building-graph-1.0-rc1",
            "graph": data,
            "integrity": self.validate(),
        }
