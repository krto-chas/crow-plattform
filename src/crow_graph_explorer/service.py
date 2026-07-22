from __future__ import annotations

from collections import Counter
from typing import Any


class GraphExplorerBuilder:
    """Build a read-only, deterministic projection of a Building Graph for Workbench."""

    def build(self, graph: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        objects = self._collection(graph, "objects")
        relations = self._collection(graph, "relations")
        properties = self._collection(graph, "properties")
        evidence = self._collection(graph, "evidence")

        object_ids = {str(item.get("id")) for item in objects if item.get("id")}
        evidence_by_id = {
            str(item["id"]): item for item in evidence if isinstance(item.get("id"), str)
        }
        properties_by_owner: dict[str, list[dict[str, Any]]] = {}
        for item in properties:
            owner_id = item.get("owner_id")
            if isinstance(owner_id, str):
                properties_by_owner.setdefault(owner_id, []).append(item)

        relation_counts: Counter[str] = Counter()
        nodes: list[dict[str, Any]] = []
        for item in sorted(objects, key=lambda row: str(row.get("id", ""))):
            object_id = str(item.get("id", ""))
            inbound = [r for r in relations if r.get("target_id") == object_id]
            outbound = [r for r in relations if r.get("source_id") == object_id]
            evidence_ids = self._string_list(item.get("evidence_ids"))
            nodes.append(
                {
                    "id": object_id,
                    "label": item.get("name") or object_id,
                    "object_type": item.get("object_type", "unknown"),
                    "discipline": item.get("discipline", "generic"),
                    "status": item.get("status", "active"),
                    "metadata": item.get("metadata", {}),
                    "property_count": len(properties_by_owner.get(object_id, [])),
                    "properties": sorted(
                        properties_by_owner.get(object_id, []),
                        key=lambda row: str(row.get("name", "")),
                    ),
                    "evidence_ids": evidence_ids,
                    "evidence": [
                        evidence_by_id[eid] for eid in evidence_ids if eid in evidence_by_id
                    ],
                    "missing_evidence_ids": [
                        eid for eid in evidence_ids if eid not in evidence_by_id
                    ],
                    "inbound_count": len(inbound),
                    "outbound_count": len(outbound),
                }
            )

        edges: list[dict[str, Any]] = []
        dangling_relation_ids: list[str] = []
        for item in sorted(relations, key=lambda row: str(row.get("id", ""))):
            relation_type = str(item.get("relation_type", "unknown"))
            relation_counts[relation_type] += 1
            source_id = str(item.get("source_id", ""))
            target_id = str(item.get("target_id", ""))
            valid = source_id in object_ids and target_id in object_ids
            if not valid:
                dangling_relation_ids.append(str(item.get("id", "")))
            evidence_ids = self._string_list(item.get("evidence_ids"))
            edges.append(
                {
                    "id": str(item.get("id", "")),
                    "source": source_id,
                    "target": target_id,
                    "relation_type": relation_type,
                    "confidence": item.get("confidence", 1.0),
                    "evidence_ids": evidence_ids,
                    "missing_evidence_ids": [
                        eid for eid in evidence_ids if eid not in evidence_by_id
                    ],
                    "valid_endpoints": valid,
                    "metadata": item.get("metadata", {}),
                }
            )

        discipline_counts = Counter(str(item.get("discipline", "generic")) for item in objects)
        object_type_counts = Counter(str(item.get("object_type", "unknown")) for item in objects)
        referenced_evidence = {
            eid
            for item in [*objects, *relations, *properties]
            for eid in self._string_list(item.get("evidence_ids"))
        }
        return {
            "nodes": nodes,
            "edges": edges,
            "evidence": sorted(evidence, key=lambda row: str(row.get("id", ""))),
            "filters": {
                "disciplines": dict(sorted(discipline_counts.items())),
                "object_types": dict(sorted(object_type_counts.items())),
                "relation_types": dict(sorted(relation_counts.items())),
            },
            "summary": {
                "objects": len(objects),
                "relations": len(relations),
                "properties": len(properties),
                "evidence": len(evidence),
                "referenced_evidence": len(referenced_evidence & set(evidence_by_id)),
                "unreferenced_evidence": len(set(evidence_by_id) - referenced_evidence),
                "dangling_relations": len(dangling_relation_ids),
            },
            "dangling_relation_ids": dangling_relation_ids,
            "metadata": {
                "read_only": True,
                "graph_mutated": False,
                "evidence_mutated": False,
                "inference_performed": False,
                "layout_persisted": False,
            },
        }

    @staticmethod
    def _collection(graph: dict[str, list[dict[str, Any]]], key: str) -> list[dict[str, Any]]:
        value = graph.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"Graph collection must be a list: {key}")
        return [item for item in value if isinstance(item, dict)]

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]
