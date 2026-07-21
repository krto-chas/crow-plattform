from __future__ import annotations

from collections import Counter
from typing import Any

from .service import BuildingGraphService, stable_id
from .system import BUILDING_LOCATION_TYPES, SYSTEM_DISCIPLINES

COMPONENT_OBJECT_TYPES = {"technical_component"}
COMPONENT_RELATIONS = {"connects_to", "feeds", "returns_to", "depends_on", "protects"}


class ComponentGraphService:
    """Domänneutral komponentgraf ovanpå Building Graph och System Graph."""

    def __init__(self, graph: BuildingGraphService):
        self.graph = graph

    def create_component(
        self,
        *,
        name: str,
        discipline: str,
        component_type: str = "generic",
        code: str | None = None,
        system_id: str | None = None,
        located_in_id: str | None = None,
        evidence_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        object_id: str | None = None,
    ) -> dict[str, Any]:
        if discipline not in SYSTEM_DISCIPLINES:
            raise ValueError(f"Okänd disciplin: {discipline}")
        if system_id:
            system = self._require_system(system_id)
            if system.get("discipline") not in {discipline, "generic"}:
                raise ValueError("Komponenten och systemet måste ha samma disciplin")
        if located_in_id:
            self._require_location(located_in_id)
        data = dict(metadata or {})
        data["component_type"] = component_type
        if code:
            data["code"] = code
        component = self.graph.create_object(
            object_id=object_id or stable_id("component", discipline, code or name),
            object_type="technical_component",
            discipline=discipline,
            name=name,
            evidence_ids=evidence_ids,
            metadata=data,
        )
        if system_id:
            self.graph.create_relation(
                source_id=component["id"],
                relation_type="belongs_to",
                target_id=system_id,
                evidence_ids=evidence_ids,
            )
            self.graph.create_relation(
                source_id=system_id,
                relation_type="contains",
                target_id=component["id"],
                evidence_ids=evidence_ids,
            )
        if located_in_id:
            self.graph.create_relation(
                source_id=component["id"],
                relation_type="located_in",
                target_id=located_in_id,
                evidence_ids=evidence_ids,
            )
        return component

    def connect_components(
        self,
        *,
        source_component_id: str,
        target_component_id: str,
        relation_type: str = "connects_to",
        evidence_ids: list[str] | None = None,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_component(source_component_id)
        self._require_component(target_component_id)
        if relation_type not in COMPONENT_RELATIONS:
            raise ValueError("Ogiltig komponentrelation")
        return self.graph.create_relation(
            source_id=source_component_id,
            relation_type=relation_type,
            target_id=target_component_id,
            evidence_ids=evidence_ids,
            confidence=confidence,
            metadata=metadata,
        )

    def add_property(
        self,
        *,
        component_id: str,
        name: str,
        value: Any,
        unit: str | None = None,
        evidence_ids: list[str] | None = None,
        confidence: float = 1.0,
    ) -> dict[str, Any]:
        self._require_component(component_id)
        return self.graph.create_property(
            owner_id=component_id,
            name=name,
            value=value,
            unit=unit,
            evidence_ids=evidence_ids,
            confidence=confidence,
        )

    def components(
        self,
        *,
        discipline: str | None = None,
        system_id: str | None = None,
        located_in_id: str | None = None,
    ) -> dict[str, Any]:
        if discipline is not None and discipline not in SYSTEM_DISCIPLINES:
            raise ValueError(f"Okänd disciplin: {discipline}")
        data = self.graph.repository.load()
        components = [
            item
            for item in data["objects"]
            if item.get("object_type") == "technical_component"
            and (discipline is None or item.get("discipline") == discipline)
        ]
        component_ids = {item["id"] for item in components}
        relations = [
            r
            for r in data["relations"]
            if r["source_id"] in component_ids or r["target_id"] in component_ids
        ]
        if system_id is not None:
            self._require_system(system_id)
            allowed = {
                r["source_id"]
                for r in relations
                if r.get("relation_type") == "belongs_to" and r.get("target_id") == system_id
            }
            components = [item for item in components if item["id"] in allowed]
        if located_in_id is not None:
            self._require_location(located_in_id)
            allowed = {
                r["source_id"]
                for r in relations
                if r.get("relation_type") == "located_in" and r.get("target_id") == located_in_id
            }
            components = [item for item in components if item["id"] in allowed]
        selected_ids = {item["id"] for item in components}
        properties = [p for p in data["properties"] if p.get("owner_id") in selected_ids]
        by_type = Counter(
            (item.get("metadata") or {}).get("component_type", "generic") for item in components
        )
        by_discipline = Counter(item.get("discipline", "generic") for item in components)
        return {
            "components": sorted(
                components,
                key=lambda item: (item.get("discipline", ""), item.get("name") or "", item["id"]),
            ),
            "relations": [
                r
                for r in relations
                if r["source_id"] in selected_ids or r["target_id"] in selected_ids
            ],
            "properties": properties,
            "summary": {
                "total": len(components),
                "by_type": dict(sorted(by_type.items())),
                "by_discipline": dict(sorted(by_discipline.items())),
                "properties": len(properties),
            },
        }

    def trace(self, component_id: str, *, max_depth: int = 20) -> dict[str, Any]:
        self._require_component(component_id)
        if max_depth < 1 or max_depth > 100:
            raise ValueError("max_depth måste ligga mellan 1 och 100")
        data = self.graph.repository.load()
        outgoing: dict[str, list[dict[str, Any]]] = {}
        for relation in data["relations"]:
            if relation.get("relation_type") in COMPONENT_RELATIONS:
                outgoing.setdefault(relation["source_id"], []).append(relation)
        visited = {component_id}
        frontier = [(component_id, 0)]
        traversed: list[dict[str, Any]] = []
        while frontier:
            current, depth = frontier.pop(0)
            if depth >= max_depth:
                continue
            for relation in outgoing.get(current, []):
                traversed.append(relation)
                target = relation["target_id"]
                if target not in visited:
                    visited.add(target)
                    frontier.append((target, depth + 1))
        objects = [o for o in data["objects"] if o["id"] in visited]
        return {
            "component_id": component_id,
            "max_depth": max_depth,
            "objects": objects,
            "relations": traversed,
            "summary": {
                "reached_components": max(0, len(objects) - 1),
                "relations": len(traversed),
            },
        }

    def _require_component(self, object_id: str) -> dict[str, Any]:
        item = self.graph.repository.get("objects", object_id)
        if item is None:
            raise KeyError(object_id)
        if item.get("object_type") != "technical_component":
            raise ValueError(f"{object_id} måste vara en teknisk komponent")
        return item

    def _require_system(self, object_id: str) -> dict[str, Any]:
        item = self.graph.repository.get("objects", object_id)
        if item is None:
            raise KeyError(object_id)
        if item.get("object_type") != "technical_system":
            raise ValueError(f"{object_id} måste vara ett tekniskt system")
        return item

    def _require_location(self, object_id: str) -> dict[str, Any]:
        item = self.graph.repository.get("objects", object_id)
        if item is None:
            raise KeyError(object_id)
        if item.get("object_type") not in BUILDING_LOCATION_TYPES:
            raise ValueError(f"{object_id} är inte en giltig byggnadsplats eller zon")
        return item
