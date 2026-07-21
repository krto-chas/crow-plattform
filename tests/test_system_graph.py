from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_building_graph import (
    BuildingGraphService,
    BuildingStructureService,
    GraphRepository,
    SystemGraphService,
)
from crow_workbench.app import create_app


def services(tmp_path: Path):
    graph = BuildingGraphService(GraphRepository(tmp_path / "graph.json"))
    return graph, BuildingStructureService(graph), SystemGraphService(graph)


def test_system_graph_creates_system_hierarchy_and_location(tmp_path: Path) -> None:
    graph, building, systems = services(tmp_path)
    house = building.create_building(name="Hus A")
    parent = systems.create_system(
        name="Ventilation", discipline="mechanical", code="VENT", located_in_id=house["id"]
    )
    child = systems.create_system(
        name="Tilluft TA01",
        discipline="mechanical",
        system_type="supply_air",
        parent_system_id=parent["id"],
    )
    result = systems.systems(discipline="mechanical")
    assert result["summary"]["total"] == 2
    assert any(
        r["relation_type"] == "contains" and r["target_id"] == child["id"]
        for r in result["relations"]
    )


def test_system_service_and_impact_traversal(tmp_path: Path) -> None:
    graph, building, systems = services(tmp_path)
    house = building.create_building(name="Hus")
    floor = building.create_floor(building_id=house["id"], name="Plan 1")
    room = building.create_space(floor_id=floor["id"], name="Rum 101")
    ahu = systems.create_system(name="AHU01", discipline="mechanical", system_type="air_handling")
    supply = systems.create_system(name="TA01", discipline="mechanical", system_type="supply_air")
    systems.connect_systems(
        source_system_id=ahu["id"], target_system_id=supply["id"], relation_type="feeds"
    )
    systems.assign_service(system_id=supply["id"], target_id=room["id"])
    impact = systems.impact(ahu["id"])
    assert {o["id"] for o in impact["objects"]} == {ahu["id"], supply["id"], room["id"]}
    assert impact["summary"]["affected_objects"] == 2


def test_system_graph_validates_discipline_and_parent(tmp_path: Path) -> None:
    _, _, systems = services(tmp_path)
    with pytest.raises(ValueError):
        systems.create_system(name="Fel", discipline="unknown")
    mechanical = systems.create_system(name="Vent", discipline="mechanical")
    with pytest.raises(ValueError):
        systems.create_system(name="El", discipline="electrical", parent_system_id=mechanical["id"])


def test_system_graph_api(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "System test", "project_id": "system-test"})
    house = client.post(
        "/api/projects/system-test/building-graph/buildings", json={"name": "Hus A"}
    ).json()
    system = client.post(
        "/api/projects/system-test/system-graph/systems",
        json={
            "name": "TA01",
            "discipline": "mechanical",
            "system_type": "supply_air",
            "located_in_id": house["id"],
        },
    )
    assert system.status_code == 201
    listing = client.get("/api/projects/system-test/system-graph/systems?discipline=mechanical")
    assert listing.status_code == 200
    assert listing.json()["summary"]["total"] == 1
    assert "mechanical" in client.get("/api/system-graph/disciplines").json()["items"]
