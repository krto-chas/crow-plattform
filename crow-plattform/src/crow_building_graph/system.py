from __future__ import annotations

from typing import Any

from .service import BuildingGraphService, stable_id

SYSTEM_OBJECT_TYPES = {"technical_system"}
SYSTEM_DISCIPLINES = {
    "mechanical",
    "electrical",
    "fire",
    "plumbing",
    "security",
    "automation",
    "generic",
}
BUILDING_LOCATION_TYPES = {"building", "floor", "space", "zone"}


class SystemGraphService:
    """Domänneutralt lager för tekniska system ovanpå Building Graph Core."""

    def __init__(self, graph: BuildingGraphService):
        self.graph = graph

    def create_system(
        self,
        *,
        name: str,
        discipline: str,
        system_type: str = "generic",
        code: str | None = None,
        parent_system_id: str | None = None,
        located_in_id: str | None = None,
        evidence_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        object_id: str | None = None,
    ) -> dict[str, Any]:
        if discipline not in SYSTEM_DISCIPLINES:
            raise ValueError(f"Okänd disciplin: {discipline}")
        if parent_system_id:
            parent = self._require_system(parent_system_id)
            if parent.get("discipline") != discipline:
                raise ValueError("Ett delsystem måste ha samma disciplin som sitt modersystem")
        if located_in_id:
            self._require_location(located_in_id)
        data = dict(metadata or {})
        data["system_type"] = system_type
        if code:
            data["code"] = code
        system = self.graph.create_object(
            object_id=object_id or stable_id("system", discipline, code or name),
            object_type="technical_system",
            discipline=discipline,
            name=name,
            evidence_ids=evidence_ids,
            metadata=data,
        )
        if parent_system_id:
            self.graph.create_relation(
                source_id=parent_system_id,
                relation_type="contains",
                target_id=system["id"],
                evidence_ids=evidence_ids,
            )
            self.graph.create_relation(
                source_id=system["id"],
                relation_type="belongs_to",
                target_id=parent_system_id,
                evidence_ids=evidence_ids,
            )
        if located_in_id:
            self.graph.create_relation(
                source_id=system["id"],
                relation_type="located_in",
                target_id=located_in_id,
                evidence_ids=evidence_ids,
            )
        return system

    def connect_systems(
        self,
        *,
        source_system_id: str,
        target_system_id: str,
        relation_type: str = "connects_to",
        evidence_ids: list[str] | None = None,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_system(source_system_id)
        self._require_system(target_system_id)
        if relation_type not in {"connects_to", "feeds", "returns_to", "depends_on"}:
            raise ValueError("Ogiltig systemsambandstyp")
        return self.graph.create_relation(
            source_id=source_system_id,
            relation_type=relation_type,
            target_id=target_system_id,
            evidence_ids=evidence_ids,
            confidence=confidence,
            metadata=metadata,
        )

    def assign_service(
        self,
        *,
        system_id: str,
        target_id: str,
        relation_type: str = "serves",
        evidence_ids: list[str] | None = None,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_system(system_id)
        self._require_location(target_id)
        if relation_type not in {"serves", "feeds", "returns_to", "protects"}:
            raise ValueError("Ogiltig betjäningsrelation")
        return self.graph.create_relation(
            source_id=system_id,
            relation_type=relation_type,
            target_id=target_id,
            evidence_ids=evidence_ids,
            confidence=confidence,
            metadata=metadata,
        )

    def systems(self, *, discipline: str | None = None) -> dict[str, Any]:
        if discipline is not None and discipline not in SYSTEM_DISCIPLINES:
            raise ValueError(f"Okänd disciplin: {discipline}")
        data = self.graph.repository.load()
        systems = [
            o
            for o in data["objects"]
            if o.get("object_type") == "technical_system"
            and (discipline is None or o.get("discipline") == discipline)
        ]
        ids = {o["id"] for o in systems}
        relations = [
            r for r in data["relations"] if r.get("source_id") in ids or r.get("target_id") in ids
        ]
        by_discipline = {
            item: sum(1 for system in systems if system.get("discipline") == item)
            for item in sorted(SYSTEM_DISCIPLINES)
        }
        return {
            "systems": sorted(
                systems,
                key=lambda item: (item.get("discipline", ""), item.get("name") or "", item["id"]),
            ),
            "relations": relations,
            "summary": {
                "total": len(systems),
                "by_discipline": by_discipline,
                "relations": len(relations),
            },
        }

    def impact(self, system_id: str, *, max_depth: int = 10) -> dict[str, Any]:
        self._require_system(system_id)
        if max_depth < 1 or max_depth > 100:
            raise ValueError("max_depth måste ligga mellan 1 och 100")
        data = self.graph.repository.load()
        outgoing: dict[str, list[dict[str, Any]]] = {}
        allowed = {
            "contains",
            "serves",
            "feeds",
            "returns_to",
            "connects_to",
            "depends_on",
            "protects",
        }
        for relation in data["relations"]:
            if relation.get("relation_type") in allowed:
                outgoing.setdefault(relation["source_id"], []).append(relation)
        visited = {system_id}
        frontier = [(system_id, 0)]
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
            "system_id": system_id,
            "max_depth": max_depth,
            "objects": objects,
            "relations": traversed,
            "summary": {"affected_objects": max(0, len(objects) - 1), "relations": len(traversed)},
        }

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
