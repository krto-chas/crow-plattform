from __future__ import annotations

from typing import Any

from .service import BuildingGraphService, stable_id

BUILDING_OBJECT_TYPES = {"building", "floor", "space", "zone"}


class BuildingStructureService:
    """Domänlager för byggnad, plan, rum och zon ovanpå grafkärnan."""

    def __init__(self, graph: BuildingGraphService):
        self.graph = graph

    def create_building(
        self,
        *,
        name: str,
        code: str | None = None,
        evidence_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        object_id: str | None = None,
    ) -> dict[str, Any]:
        data = dict(metadata or {})
        if code:
            data["code"] = code
        return self.graph.create_object(
            object_id=object_id or stable_id("building", code or name),
            object_type="building",
            discipline="building",
            name=name,
            evidence_ids=evidence_ids,
            metadata=data,
        )

    def create_floor(
        self,
        *,
        building_id: str,
        name: str,
        level: float | None = None,
        code: str | None = None,
        evidence_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        object_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_type(building_id, "building")
        data = dict(metadata or {})
        if code:
            data["code"] = code
        if level is not None:
            data["level"] = level
        floor = self.graph.create_object(
            object_id=object_id or stable_id("floor", building_id, code or name),
            object_type="floor",
            discipline="building",
            name=name,
            evidence_ids=evidence_ids,
            metadata=data,
        )
        self.graph.create_relation(
            source_id=building_id,
            relation_type="contains",
            target_id=floor["id"],
            evidence_ids=evidence_ids,
        )
        return floor

    def create_space(
        self,
        *,
        floor_id: str,
        name: str,
        number: str | None = None,
        area: float | None = None,
        area_unit: str = "m2",
        evidence_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        object_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_type(floor_id, "floor")
        if area is not None and area < 0:
            raise ValueError("Rumsarea får inte vara negativ")
        data = dict(metadata or {})
        if number:
            data["number"] = number
        space = self.graph.create_object(
            object_id=object_id or stable_id("space", floor_id, number or name),
            object_type="space",
            discipline="building",
            name=name,
            evidence_ids=evidence_ids,
            metadata=data,
        )
        self.graph.create_relation(
            source_id=floor_id,
            relation_type="contains",
            target_id=space["id"],
            evidence_ids=evidence_ids,
        )
        self.graph.create_relation(
            source_id=space["id"],
            relation_type="located_in",
            target_id=floor_id,
            evidence_ids=evidence_ids,
        )
        if area is not None:
            self.graph.create_property(
                owner_id=space["id"],
                name="area",
                value=area,
                unit=area_unit,
                evidence_ids=evidence_ids,
            )
        return space

    def create_zone(
        self,
        *,
        name: str,
        space_ids: list[str],
        zone_type: str = "generic",
        evidence_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        object_id: str | None = None,
    ) -> dict[str, Any]:
        if not space_ids:
            raise ValueError("En zon måste innehålla minst ett rum")
        for space_id in space_ids:
            self._require_type(space_id, "space")
        data = dict(metadata or {})
        data["zone_type"] = zone_type
        zone = self.graph.create_object(
            object_id=object_id or stable_id("zone", zone_type, name, *sorted(space_ids)),
            object_type="zone",
            discipline="building",
            name=name,
            evidence_ids=evidence_ids,
            metadata=data,
        )
        for space_id in space_ids:
            self.graph.create_relation(
                source_id=zone["id"],
                relation_type="contains",
                target_id=space_id,
                evidence_ids=evidence_ids,
            )
            self.graph.create_relation(
                source_id=space_id,
                relation_type="belongs_to",
                target_id=zone["id"],
                evidence_ids=evidence_ids,
            )
        return zone

    def structure(self) -> dict[str, Any]:
        data = self.graph.repository.load()
        objects = {
            item["id"]: item
            for item in data["objects"]
            if item.get("object_type") in BUILDING_OBJECT_TYPES
        }
        contains = [
            r
            for r in data["relations"]
            if r.get("relation_type") == "contains"
            and r.get("source_id") in objects
            and r.get("target_id") in objects
        ]
        children: dict[str, list[str]] = {}
        for relation in contains:
            children.setdefault(relation["source_id"], []).append(relation["target_id"])

        def node(object_id: str) -> dict[str, Any]:
            item = dict(objects[object_id])
            item["children"] = [node(child_id) for child_id in sorted(children.get(object_id, []))]
            return item

        roots = [item_id for item_id, item in objects.items() if item["object_type"] == "building"]
        return {
            "buildings": [node(item_id) for item_id in sorted(roots)],
            "summary": {
                kind: sum(1 for item in objects.values() if item["object_type"] == kind)
                for kind in ("building", "floor", "space", "zone")
            },
        }

    def _require_type(self, object_id: str, expected: str) -> dict[str, Any]:
        item = self.graph.repository.get("objects", object_id)
        if item is None:
            raise KeyError(object_id)
        if item.get("object_type") != expected:
            raise ValueError(f"{object_id} måste vara av typen {expected}")
        return item
