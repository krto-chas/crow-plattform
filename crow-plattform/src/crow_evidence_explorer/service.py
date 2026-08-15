from __future__ import annotations

from collections import Counter
from typing import Any


class EvidenceExplorerBuilder:
    """Build a read-only evidence-centric projection of a Building Graph."""

    def build(self, graph: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        objects = self._collection(graph, "objects")
        relations = self._collection(graph, "relations")
        properties = self._collection(graph, "properties")
        evidence = self._collection(graph, "evidence")

        evidence_by_id: dict[str, dict[str, Any]] = {}
        duplicate_ids: set[str] = set()
        for item in evidence:
            evidence_id = item.get("id")
            if not isinstance(evidence_id, str) or not evidence_id:
                continue
            if evidence_id in evidence_by_id:
                duplicate_ids.add(evidence_id)
                continue
            evidence_by_id[evidence_id] = item

        references: dict[str, list[dict[str, Any]]] = {
            evidence_id: [] for evidence_id in evidence_by_id
        }
        missing_references: list[dict[str, str]] = []
        for entity_kind, rows in (
            ("object", objects),
            ("relation", relations),
            ("property", properties),
        ):
            for row in rows:
                entity_id = str(row.get("id", ""))
                label = self._label(entity_kind, row)
                for evidence_id in self._string_list(row.get("evidence_ids")):
                    reference = {
                        "entity_kind": entity_kind,
                        "entity_id": entity_id,
                        "label": label,
                    }
                    if evidence_id in references:
                        references[evidence_id].append(reference)
                    else:
                        missing_references.append(
                            {
                                "evidence_id": evidence_id,
                                "entity_kind": entity_kind,
                                "entity_id": entity_id,
                                "label": label,
                            }
                        )

        kinds: Counter[str] = Counter()
        sources: Counter[str] = Counter()
        items: list[dict[str, Any]] = []
        for evidence_id in sorted(evidence_by_id):
            item = evidence_by_id[evidence_id]
            kind = str(item.get("kind", "unknown"))
            source_id = str(item.get("source_id", "unknown"))
            kinds[kind] += 1
            sources[source_id] += 1
            item_references = sorted(
                references[evidence_id],
                key=lambda row: (row["entity_kind"], row["entity_id"]),
            )
            items.append(
                {
                    "id": evidence_id,
                    "kind": kind,
                    "source_id": source_id,
                    "locator": item.get("locator"),
                    "checksum": item.get("checksum"),
                    "confidence": item.get("confidence", 1.0),
                    "metadata": item.get("metadata", {}),
                    "reference_count": len(item_references),
                    "references": item_references,
                    "status": "referenced" if item_references else "unreferenced",
                }
            )

        return {
            "items": items,
            "missing_references": sorted(
                missing_references,
                key=lambda row: (row["evidence_id"], row["entity_kind"], row["entity_id"]),
            ),
            "duplicate_evidence_ids": sorted(duplicate_ids),
            "filters": {
                "kinds": dict(sorted(kinds.items())),
                "sources": dict(sorted(sources.items())),
                "statuses": {
                    "referenced": sum(1 for item in items if item["status"] == "referenced"),
                    "unreferenced": sum(1 for item in items if item["status"] == "unreferenced"),
                },
            },
            "summary": {
                "evidence": len(items),
                "referenced": sum(1 for item in items if item["status"] == "referenced"),
                "unreferenced": sum(1 for item in items if item["status"] == "unreferenced"),
                "references": sum(item["reference_count"] for item in items),
                "missing_references": len(missing_references),
                "duplicate_evidence_ids": len(duplicate_ids),
            },
            "metadata": {
                "read_only": True,
                "graph_mutated": False,
                "evidence_mutated": False,
                "inference_performed": False,
                "automatic_repair_performed": False,
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
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("evidence_ids must be a list")
        return [item for item in value if isinstance(item, str) and item]

    @staticmethod
    def _label(entity_kind: str, row: dict[str, Any]) -> str:
        if entity_kind == "object":
            return str(row.get("name") or row.get("id") or "")
        if entity_kind == "relation":
            return str(row.get("relation_type") or row.get("id") or "")
        return str(row.get("name") or row.get("id") or "")
