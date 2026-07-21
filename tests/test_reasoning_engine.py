from pathlib import Path

from crow_building_graph.repository import GraphRepository
from crow_building_graph.service import BuildingGraphService
from crow_reasoning import ReasoningService, TraversalEngine


def graph_fixture(tmp_path: Path):
    path = tmp_path / "graph.json"
    service = BuildingGraphService(GraphRepository(path))
    for oid, typ in (
        ("ahu", "technical_system"),
        ("ta", "technical_system"),
        ("td", "component"),
        ("room", "space"),
        ("lonely", "component"),
    ):
        service.create_object(object_id=oid, object_type=typ, name=oid)
    service.create_relation(source_id="ahu", relation_type="feeds", target_id="ta")
    service.create_relation(source_id="ta", relation_type="feeds", target_id="td")
    service.create_relation(source_id="td", relation_type="serves", target_id="room")
    return path


def test_downstream_and_shortest_path(tmp_path):
    engine = ReasoningService(graph_fixture(tmp_path)).engine()
    result = engine.downstream("ahu", relation_types={"feeds", "serves"})
    assert [s.object_id for s in result.steps] == ["ahu", "ta", "td", "room"]
    path = engine.shortest_path(
        "ahu", "room", relation_types={"feeds", "serves"}, direction="outgoing"
    )
    assert path.found and path.object_ids == ("ahu", "ta", "td", "room")


def test_impact_and_diagnostics(tmp_path):
    service = ReasoningService(graph_fixture(tmp_path))
    impact = service.impact("ahu")
    assert impact["affected_count"] == 3
    diagnostics = service.diagnostics()
    assert diagnostics["summary"]["isolated_objects"] == 1
    assert diagnostics["summary"]["dead_ends"] == 1


def test_cycle_detection():
    graph = {
        "objects": [{"id": x} for x in "abc"],
        "relations": [
            {"id": "ab", "source_id": "a", "target_id": "b", "relation_type": "feeds"},
            {"id": "bc", "source_id": "b", "target_id": "c", "relation_type": "feeds"},
            {"id": "ca", "source_id": "c", "target_id": "a", "relation_type": "feeds"},
        ],
    }
    cycles = TraversalEngine(graph).cycles()
    assert len(cycles) == 1
    assert cycles[0].severity == "error"
