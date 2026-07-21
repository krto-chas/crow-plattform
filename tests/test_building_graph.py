from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_building_graph import (
    BuildingGraphService,
    BuildingStructureService,
    ComponentGraphService,
    GraphRepository,
    SystemGraphService,
)
from crow_workbench.app import create_app


def service(tmp_path: Path) -> BuildingGraphService:
    return BuildingGraphService(GraphRepository(tmp_path / "graph.json"))


def test_graph_core_creates_evidence_objects_relations_and_properties(tmp_path: Path) -> None:
    graph = service(tmp_path)
    evidence = graph.create_evidence(kind="dwg", source_id="drawing-1", locator="block:42")
    room = graph.create_object(
        object_id="room:201", object_type="space", name="Rum 201", evidence_ids=[evidence["id"]]
    )
    diffuser = graph.create_object(
        object_id="vent:td101", object_type="supply_diffuser", discipline="vent", name="TD101"
    )
    relation = graph.create_relation(
        source_id=diffuser["id"],
        relation_type="located_in",
        target_id=room["id"],
        evidence_ids=[evidence["id"]],
        confidence=0.95,
    )
    prop = graph.create_property(
        owner_id=diffuser["id"], name="flow", value=80, unit="l/s", evidence_ids=[evidence["id"]]
    )

    payload = graph.graph()
    assert payload["summary"]["objects"] == 2
    assert relation["relation_type"] == "located_in"
    assert prop["unit"] == "l/s"
    assert payload["summary"]["history"] == 4


def test_object_update_creates_new_revision_and_history(tmp_path: Path) -> None:
    graph = service(tmp_path)
    graph.create_object(object_id="object:1", object_type="building", name="A")
    updated = graph.update_object(
        "object:1", name="Hus A", metadata={"external_id": "A01"}, actor="reviewer"
    )
    assert updated["revision"] == 2
    assert updated["name"] == "Hus A"
    history = graph.graph()["history"]
    assert history[-1]["actor"] == "reviewer"
    assert history[-1]["revision"] == 2


def test_graph_rejects_invalid_references_and_confidence(tmp_path: Path) -> None:
    graph = service(tmp_path)
    graph.create_object(object_id="a", object_type="space")
    with pytest.raises(KeyError):
        graph.create_relation(source_id="a", relation_type="contains", target_id="missing")
    with pytest.raises(ValueError):
        graph.create_evidence(kind="manual", source_id="review", confidence=1.1)
    with pytest.raises(ValueError):
        graph.create_relation(source_id="a", relation_type="invented", target_id="a")


def test_neighbor_query_returns_connected_objects(tmp_path: Path) -> None:
    graph = service(tmp_path)
    graph.create_object(object_id="building:a", object_type="building")
    graph.create_object(object_id="floor:1", object_type="floor")
    graph.create_relation(source_id="building:a", relation_type="contains", target_id="floor:1")
    result = graph.neighbors("building:a")
    assert [item["id"] for item in result["objects"]] == ["floor:1"]


def test_building_graph_api_persists_per_project(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    assert (
        client.post(
            "/api/projects", json={"name": "Graph test", "project_id": "graph-test"}
        ).status_code
        == 201
    )
    evidence = client.post(
        "/api/projects/graph-test/graph/evidence", json={"kind": "manual", "source_id": "review-1"}
    )
    assert evidence.status_code == 201
    object_response = client.post(
        "/api/projects/graph-test/graph/objects",
        json={
            "object_id": "building:1",
            "object_type": "building",
            "name": "Hus 1",
            "evidence_ids": [evidence.json()["id"]],
        },
    )
    assert object_response.status_code == 201
    graph = client.get("/api/projects/graph-test/graph")
    assert graph.status_code == 200
    assert graph.json()["summary"]["objects"] == 1
    assert client.get("/api/graph/relation-types").json()["count"] >= 10




def test_building_structure_creates_hierarchy_and_area(tmp_path: Path) -> None:
    graph = service(tmp_path)
    building = BuildingStructureService(graph)
    house = building.create_building(name="Hus A", code="A")
    floor = building.create_floor(building_id=house["id"], name="Plan 2", level=2)
    room = building.create_space(floor_id=floor["id"], name="Kontor", number="201", area=18.5)
    tree = building.structure()
    assert tree["summary"] == {"building": 1, "floor": 1, "space": 1, "zone": 0}
    assert tree["buildings"][0]["children"][0]["children"][0]["id"] == room["id"]
    assert (
        next(item for item in graph.graph()["properties"] if item["owner_id"] == room["id"])[
            "value"
        ]
        == 18.5
    )


def test_zone_requires_spaces_and_creates_membership(tmp_path: Path) -> None:
    graph = service(tmp_path)
    building = BuildingStructureService(graph)
    house = building.create_building(name="Hus")
    floor = building.create_floor(building_id=house["id"], name="Plan 1")
    room = building.create_space(floor_id=floor["id"], name="Rum 101")
    zone = building.create_zone(name="Kontorszon", zone_type="ventilation", space_ids=[room["id"]])
    neighbors = graph.neighbors(zone["id"], "contains")
    assert neighbors["objects"][0]["id"] == room["id"]


def test_building_structure_rejects_wrong_parent_and_negative_area(tmp_path: Path) -> None:
    graph = service(tmp_path)
    building = BuildingStructureService(graph)
    house = building.create_building(name="Hus")
    with pytest.raises(ValueError):
        building.create_space(floor_id=house["id"], name="Fel rum")
    floor = building.create_floor(building_id=house["id"], name="Plan")
    with pytest.raises(ValueError):
        building.create_space(floor_id=floor["id"], name="Fel area", area=-1)


def test_building_structure_api(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Building test", "project_id": "building-test"})
    house = client.post(
        "/api/projects/building-test/building-graph/buildings", json={"name": "Hus A", "code": "A"}
    )
    assert house.status_code == 201
    floor = client.post(
        "/api/projects/building-test/building-graph/floors",
        json={"building_id": house.json()["id"], "name": "Plan 1", "level": 1},
    )
    assert floor.status_code == 201
    room = client.post(
        "/api/projects/building-test/building-graph/spaces",
        json={"floor_id": floor.json()["id"], "name": "Kontor", "number": "101", "area": 12.0},
    )
    assert room.status_code == 201
    structure = client.get("/api/projects/building-test/building-graph/structure")
    assert structure.status_code == 200
    assert structure.json()["summary"]["space"] == 1




def test_component_graph_creates_component_with_system_and_location(tmp_path: Path) -> None:
    graph = service(tmp_path)
    building = BuildingStructureService(graph)
    systems = SystemGraphService(graph)
    components = ComponentGraphService(graph)
    house = building.create_building(name="Hus")
    floor = building.create_floor(building_id=house["id"], name="Plan 1")
    room = building.create_space(floor_id=floor["id"], name="Rum 101")
    system = systems.create_system(name="Tilluft", discipline="mechanical", code="TA01")
    component = components.create_component(
        name="Tilluftsdon",
        discipline="mechanical",
        component_type="supply_diffuser",
        code="TD101",
        system_id=system["id"],
        located_in_id=room["id"],
    )
    result = components.components(system_id=system["id"])
    assert result["components"][0]["id"] == component["id"]
    assert result["summary"]["by_type"] == {"supply_diffuser": 1}


def test_component_graph_properties_and_trace(tmp_path: Path) -> None:
    graph = service(tmp_path)
    components = ComponentGraphService(graph)
    first = components.create_component(name="Fläkt", discipline="mechanical", component_type="fan")
    second = components.create_component(
        name="Ljuddämpare", discipline="mechanical", component_type="silencer"
    )
    components.connect_components(
        source_component_id=first["id"], target_component_id=second["id"], relation_type="feeds"
    )
    prop = components.add_property(component_id=first["id"], name="flow", value=1200, unit="l/s")
    trace = components.trace(first["id"])
    assert prop["unit"] == "l/s"
    assert trace["summary"] == {"reached_components": 1, "relations": 1}


def test_component_graph_rejects_discipline_mismatch(tmp_path: Path) -> None:
    graph = service(tmp_path)
    systems = SystemGraphService(graph)
    components = ComponentGraphService(graph)
    system = systems.create_system(name="El", discipline="electrical")
    with pytest.raises(ValueError):
        components.create_component(name="Don", discipline="mechanical", system_id=system["id"])


def test_component_graph_api(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Component test", "project_id": "component-test"})
    system = client.post(
        "/api/projects/component-test/system-graph/systems",
        json={"name": "TA01", "discipline": "mechanical"},
    )
    component = client.post(
        "/api/projects/component-test/component-graph/components",
        json={
            "name": "TD101",
            "discipline": "mechanical",
            "component_type": "supply_diffuser",
            "system_id": system.json()["id"],
        },
    )
    assert component.status_code == 201
    listed = client.get(
        "/api/projects/component-test/component-graph/components",
        params={"system_id": system.json()["id"]},
    )
    assert listed.status_code == 200
    assert listed.json()["summary"]["total"] == 1
    assert client.get("/api/component-graph/relation-types").json()["count"] == 5
