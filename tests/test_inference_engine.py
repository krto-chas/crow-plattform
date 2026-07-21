from __future__ import annotations

import json
from pathlib import Path

from crow_inference import InferenceEngine, InferenceService


def graph() -> dict:
    return {
        "revision": 4,
        "objects": [
            {"id": "TD101", "object_type": "component"},
            {"id": "TA01", "object_type": "system"},
            {"id": "AHU01", "object_type": "system"},
        ],
        "relations": [
            {
                "id": "r1",
                "source_id": "TD101",
                "relation_type": "served_by",
                "target_id": "TA01",
                "confidence": 0.98,
            },
            {
                "id": "r2",
                "source_id": "TA01",
                "relation_type": "served_by",
                "target_id": "AHU01",
                "confidence": 0.97,
            },
        ],
        "properties": [],
        "evidence": [],
        "history": [],
    }


def test_infers_transitive_relation_with_explanation() -> None:
    result = InferenceEngine(graph()).infer()
    relation = next(item for item in result["derived_relations"] if item["source_id"] == "TD101")
    assert relation["target_id"] == "AHU01"
    assert relation["relation_type"] == "indirectly_served_by"
    assert [step["relation_id"] for step in relation["explanation"]] == ["r1", "r2"]
    assert 0 < relation["confidence"] < 0.98


def test_does_not_duplicate_explicit_conclusion() -> None:
    payload = graph()
    payload["relations"].append(
        {
            "id": "r3",
            "source_id": "TD101",
            "relation_type": "indirectly_served_by",
            "target_id": "AHU01",
        }
    )
    result = InferenceEngine(payload).infer()
    assert not any(
        item["source_id"] == "TD101" and item["target_id"] == "AHU01"
        for item in result["derived_relations"]
    )


def test_detects_conflicting_properties() -> None:
    payload = graph()
    payload["properties"] = [
        {
            "id": "p1",
            "owner_id": "TD101",
            "name": "dimension",
            "value": "Ø160",
            "evidence_ids": ["e1"],
        },
        {
            "id": "p2",
            "owner_id": "TD101",
            "name": "dimension",
            "value": "Ø200",
            "evidence_ids": ["e2"],
        },
    ]
    conflicts = InferenceEngine(payload).detect_property_conflicts()
    assert len(conflicts) == 1
    assert conflicts[0].predicate == "dimension"
    assert conflicts[0].evidence_ids == ("e1", "e2")


def test_service_persists_result(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph()), encoding="utf-8")
    service = InferenceService(graph_path)
    result = service.run()
    assert result["summary"]["derived_relations"] == 1
    assert (tmp_path / "inferences.json").exists()
    assert service.list()["schema"] == "crow-inference-v0.3"


def test_explain_unknown_relation_raises(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph()), encoding="utf-8")
    service = InferenceService(graph_path)
    service.run()
    try:
        service.explain("missing")
    except KeyError:
        pass
    else:
        raise AssertionError("KeyError expected")


def test_fuses_evidence_from_relation_chain() -> None:
    payload = graph()
    payload["relations"][0]["evidence_ids"] = ["dwg-1"]
    payload["relations"][1]["evidence_ids"] = ["ifc-1", "pdf-1"]
    result = InferenceEngine(payload).infer()
    relation = next(item for item in result["derived_relations"] if item["source_id"] == "TD101")
    assert relation["evidence_ids"] == ["dwg-1", "ifc-1", "pdf-1"]
    assert relation["metadata"]["evidence_fused"] is True


def test_rule_chaining_can_use_derived_facts() -> None:
    payload = graph()
    rules = [
        {
            "id": "rule.indirect",
            "premise_relation": "served_by",
            "conclusion_relation": "indirectly_served_by",
        },
        {
            "id": "rule.reaches",
            "premise_relation": "indirectly_served_by",
            "conclusion_relation": "reaches",
        },
    ]
    from crow_inference import InferenceRule

    selected = [InferenceRule(**item) for item in rules]
    result = InferenceEngine(payload).infer(selected, max_iterations=4)
    assert any(
        item["relation_type"] == "indirectly_served_by" for item in result["derived_relations"]
    )


def test_query_filters_derived_relations() -> None:
    engine = InferenceEngine(graph())
    result = engine.infer()
    matches = engine.query(
        result, source_id="TD101", relation_type="indirectly_served_by", minimum_confidence=0.5
    )
    assert len(matches) == 1
    assert matches[0]["target_id"] == "AHU01"


def test_service_exposes_conflicts_and_query(tmp_path: Path) -> None:
    payload = graph()
    payload["properties"] = [
        {"id": "p1", "owner_id": "TD101", "name": "dimension", "value": "Ø160"},
        {"id": "p2", "owner_id": "TD101", "name": "dimension", "value": "Ø200"},
    ]
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(payload), encoding="utf-8")
    service = InferenceService(graph_path)
    service.run()
    assert service.conflicts()["count"] == 1
    assert service.query(source_id="TD101")["count"] == 1


def test_schema_upgraded_to_v02() -> None:
    result = InferenceEngine(graph()).infer()
    assert result["schema"] == "crow-inference-v0.2"
    assert result["summary"]["iterations"] >= 1


def test_lifecycle_detects_stale_graph_and_reruns(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph()), encoding="utf-8")
    service = InferenceService(graph_path)
    first = service.run()
    assert first["run_number"] == 1
    assert service.status()["status"] == "current"
    payload = graph()
    payload["relations"].pop()
    payload["revision"] = 5
    graph_path.write_text(json.dumps(payload), encoding="utf-8")
    assert service.status()["status"] == "stale"
    second = service.run()
    assert second["run_number"] == 2
    assert second["diff"]["counts"]["removed_relations"] == 1


def test_unchanged_run_uses_cache_without_new_history_entry(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph()), encoding="utf-8")
    service = InferenceService(graph_path)
    service.run()
    cached = service.run()
    assert cached["cache"]["hit"] is True
    assert len(service.history()["runs"]) == 1


def test_manual_invalidation_and_force_run(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph()), encoding="utf-8")
    service = InferenceService(graph_path)
    service.run()
    invalidated = service.invalidate(reason="source_reimported")
    assert invalidated["invalidated"] is True
    assert service.list()["lifecycle_status"] == "stale"
    rerun = service.run(force=True)
    assert rerun["run_number"] == 2


def test_history_and_adjacent_diff(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph()), encoding="utf-8")
    service = InferenceService(graph_path)
    service.run()
    payload = graph()
    payload["relations"].pop()
    graph_path.write_text(json.dumps(payload), encoding="utf-8")
    service.run()
    history = service.history()
    assert [item["run_number"] for item in history["runs"]] == [1, 2]
    comparison = service.diff(from_run=1, to_run=2)
    assert comparison["diff"]["counts"]["removed_relations"] == 1


def test_schema_upgraded_to_v03_on_persisted_run(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph()), encoding="utf-8")
    result = InferenceService(graph_path).run()
    assert result["schema"] == "crow-inference-v0.3"
    assert result["graph_fingerprint"]
    assert result["rule_fingerprint"]
