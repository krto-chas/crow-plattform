from pathlib import Path

from crow_building_graph import BuildingGraphService, GraphRepository
from crow_canonical import CanonicalGraphBridge, CanonicalObjectType, VentCanonicalAdapter
from crow_vent import VentTextInterpreter


def test_duct_interpretation_becomes_canonical_object() -> None:
    interpretation = VentTextInterpreter().interpret(
        "T13-250x400-V1",
        source_id="drawing-1",
        layer="V-57--",
        entity_handle="ABC1",
    )
    canonical = VentCanonicalAdapter().convert(interpretation)
    assert canonical is not None
    assert canonical.object_type is CanonicalObjectType.DUCT
    assert canonical.properties["medium"] == "Tilluft"
    assert canonical.properties["width_mm"] == 250
    assert canonical.evidence.locator == "ABC1"


def test_component_category_maps_to_canonical_type() -> None:
    interpretation = VentTextInterpreter().interpret(
        "TD1", source_id="drawing-1", layer="DON", entity_handle="D1"
    )
    canonical = VentCanonicalAdapter().convert(interpretation)
    assert canonical is not None
    assert canonical.object_type is CanonicalObjectType.AIR_TERMINAL
    assert canonical.properties["code"] == "TD"


def test_unknown_text_is_not_forced_into_ccm() -> None:
    interpretation = VentTextInterpreter().interpret(
        "HELT OKÄND", source_id="drawing-1", layer="MYSTERY"
    )
    assert VentCanonicalAdapter().convert(interpretation) is None


def test_canonical_object_persists_with_shared_evidence(tmp_path: Path) -> None:
    interpretation = VentTextInterpreter().interpret(
        "T13-250x400-V1",
        source_id="drawing-1",
        layer="V-57--",
        entity_handle="ABC1",
    )
    canonical = VentCanonicalAdapter().convert(interpretation)
    assert canonical is not None
    graph = BuildingGraphService(GraphRepository(tmp_path / "graph.json"))
    result = CanonicalGraphBridge(graph).persist(canonical)

    assert result["object"]["object_type"] == "duct"
    evidence_id = result["evidence"]["id"]
    assert result["object"]["evidence_ids"] == (evidence_id,)
    assert result["properties"]
    assert all(item["evidence_ids"] == (evidence_id,) for item in result["properties"])
    assert graph.graph()["summary"]["objects"] == 1
