from __future__ import annotations

from collections import defaultdict
from typing import Any


class CrossSourceLinkBuilder:
    """Link objects only when an explicit shared external identity is present."""

    def build(self, graph: dict[str, Any]) -> dict[str, Any]:
        project_id = str(graph.get("project_id", "unknown"))
        objects = graph.get("objects", [])
        if not isinstance(objects, list):
            raise ValueError("Graph objects must be a list")
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for obj in objects:
            if not isinstance(obj, dict):
                raise ValueError("Graph object must be an object")
            metadata = obj.get("metadata", {})
            if not isinstance(metadata, dict):
                continue
            external_id = metadata.get("external_id")
            source_id = metadata.get("source_id")
            object_id = obj.get("object_id")
            if all(isinstance(v, str) and v for v in (external_id, source_id, object_id)):
                groups[str(external_id)].append(
                    {"object_id": str(object_id), "source_id": str(source_id)}
                )
        links = []
        for external_id, refs in sorted(groups.items()):
            if len({r["source_id"] for r in refs}) < 2:
                continue
            references = list(refs)
            references.sort(key=self._reference_key)
            links.append(
                {
                    "link_id": f"external:{external_id}",
                    "external_id": external_id,
                    "references": references,
                    "basis": "explicit_external_id",
                    "status": "candidate",
                }
            )
        return {
            "project_id": project_id,
            "links": links,
            "summary": {
                "candidates": len(links),
                "objects_linked": sum(len(x["references"]) for x in links),
            },
            "metadata": {
                "read_only": True,
                "automatic_merge_performed": False,
                "inference_performed": False,
            },
        }

    @staticmethod
    def _reference_key(item: dict[str, str]) -> tuple[str, str]:
        return item.get("source_id", ""), item.get("object_id", "")
