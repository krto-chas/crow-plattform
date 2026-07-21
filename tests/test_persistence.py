from pathlib import Path

from crow_module_sdk import (
    ComputationFingerprint,
    JsonDecisionGraphRepository,
    JsonFingerprintRepository,
)
from crow_module_sdk.decision_graph import DecisionGraph, GraphEdge, GraphNode, Relation


def test_decision_graph_round_trips_through_json(tmp_path: Path) -> None:
    graph = DecisionGraph()
    graph.add_node(GraphNode("claim-1", "claim"))
    graph.add_node(GraphNode("decision-1", "decision"))
    graph.add_edge(GraphEdge("claim-1", Relation.SUPPORTS, "decision-1"))

    repository = JsonDecisionGraphRepository(tmp_path / "graphs")
    repository.save("project-1", graph)
    loaded = repository.load("project-1")

    assert loaded is not None
    assert loaded.nodes == graph.nodes
    assert loaded.edges == graph.edges


def test_fingerprint_repository_round_trip(tmp_path: Path) -> None:
    repository = JsonFingerprintRepository(tmp_path / "fingerprints.json")
    fingerprint = ComputationFingerprint.from_payload({"value": 1})

    repository.save(fingerprint, "decision-result:123")
    stored = repository.find(fingerprint)

    assert stored is not None
    assert stored.result_reference == "decision-result:123"
