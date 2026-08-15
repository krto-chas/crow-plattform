from pathlib import Path

from crow_building_graph import (
    BuildingGraphService,
    BuildingStructureService,
    ComponentGraphService,
    GraphIntegrityService,
    GraphRepository,
    SystemGraphService,
)


def test_rc1_end_to_end(tmp_path: Path) -> None:
    graph = BuildingGraphService(GraphRepository(tmp_path / "graph.json"))
    building = BuildingStructureService(graph)
    systems = SystemGraphService(graph)
    components = ComponentGraphService(graph)
    integrity = GraphIntegrityService(graph)

    evidence = graph.create_evidence(kind="ifc", source_id="V-50-1-01.ifc", checksum="abc")
    house = building.create_building(name="Hus A", code="A", evidence_ids=[evidence["id"]])
    floor = building.create_floor(
        building_id=house["id"], name="Plan 1", code="01", evidence_ids=[evidence["id"]]
    )
    room = building.create_space(
        floor_id=floor["id"], name="Rum 101", number="101", area=24.5, evidence_ids=[evidence["id"]]
    )
    system = systems.create_system(
        name="Tilluft 01",
        discipline="mechanical",
        code="TA01",
        located_in_id=floor["id"],
        evidence_ids=[evidence["id"]],
    )
    systems.assign_service(
        system_id=system["id"], target_id=room["id"], evidence_ids=[evidence["id"]]
    )
    component = components.create_component(
        name="Don 101",
        discipline="mechanical",
        component_type="supply_diffuser",
        code="TD101",
        system_id=system["id"],
        located_in_id=room["id"],
        evidence_ids=[evidence["id"]],
    )
    components.add_property(
        component_id=component["id"],
        name="dimension",
        value=160,
        unit="mm",
        evidence_ids=[evidence["id"]],
    )

    result = integrity.validate()
    assert result["valid"] is True
    assert result["summary"]["objects"] == 5
    assert result["summary"]["errors"] == 0

    traversal = integrity.traverse(system["id"], relation_types={"contains", "serves"})
    reached = {item["id"] for item in traversal["objects"]}
    assert room["id"] in reached
    assert component["id"] in reached

    snapshot = integrity.export_snapshot()
    assert snapshot["schema"] == "crow-building-graph-1.0-rc1"
    assert snapshot["integrity"]["valid"] is True


def test_integrity_warns_about_orphan_component(tmp_path: Path) -> None:
    graph = BuildingGraphService(GraphRepository(tmp_path / "graph.json"))
    components = ComponentGraphService(graph)
    components.create_component(name="Lös komponent", discipline="mechanical")
    result = GraphIntegrityService(graph).validate()
    assert result["valid"] is True
    assert result["summary"]["warnings"] == 1
    assert result["issues"][0]["code"] == "component_without_system"
