import json
from pathlib import Path

import pytest

from crow_building_graph.repository import GraphRepository
from crow_building_graph.service import BuildingGraphService
from crow_reasoning import RuleDefinition, RuleEngine, RuleService


def build_graph(tmp_path: Path) -> Path:
    path = tmp_path / "graph.json"
    service = BuildingGraphService(GraphRepository(path))
    evidence = service.create_evidence(kind="manual", source_id="review", evidence_id="ev1")
    service.create_object(
        object_id="sys", object_type="technical_system", discipline="mechanical", name="TA01"
    )
    service.create_object(
        object_id="ok",
        object_type="component",
        discipline="mechanical",
        name="TD101",
        evidence_ids=[evidence["id"]],
    )
    service.create_object(
        object_id="bad", object_type="component", discipline="mechanical", name="TD102"
    )
    service.create_relation(source_id="ok", relation_type="belongs_to", target_id="sys")
    service.create_property(
        owner_id="ok", name="dimension", value="160", unit="mm", evidence_ids=[evidence["id"]]
    )
    return path


def test_rule_engine_generates_stable_findings(tmp_path):
    graph = GraphRepository(build_graph(tmp_path)).load()
    rule = {
        "id": "vent.component.system",
        "version": "1.0.0",
        "title": "System saknas",
        "selector": {"object_type": "component", "discipline": "mechanical"},
        "requirements": [
            {
                "kind": "relation",
                "relation_type": "belongs_to",
                "direction": "outgoing",
                "target_object_type": "technical_system",
            }
        ],
        "severity": "error",
        "confidence": 0.95,
    }
    result = RuleEngine(graph).evaluate([rule])
    assert result["summary"]["finding_count"] == 1
    finding = result["findings"][0]
    assert finding["object_id"] == "bad"
    assert finding["severity"] == "error"
    assert finding["id"].startswith("finding:")


def test_property_and_evidence_requirements(tmp_path):
    graph = GraphRepository(build_graph(tmp_path)).load()
    rules = [
        {
            "id": "dimension",
            "title": "Dimension saknas",
            "selector": {"object_type": "component"},
            "requirements": [
                {
                    "kind": "property",
                    "property_name": "dimension",
                    "operator": "exists",
                    "evidence_required": True,
                }
            ],
            "severity": "warning",
        }
    ]
    result = RuleEngine(graph).evaluate(rules)
    assert [f["object_id"] for f in result["findings"]] == ["bad"]


def test_rule_service_loads_json_pack(tmp_path):
    graph_path = build_graph(tmp_path)
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "evidence",
                        "title": "Evidens saknas",
                        "selector": {"object_type": "component"},
                        "requirements": [{"kind": "evidence", "operator": "exists"}],
                        "severity": "info",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    service = RuleService(graph_path, rules_path)
    assert service.validate_rules()["rule_count"] == 1
    assert service.evaluate()["summary"]["finding_count"] == 1


def test_invalid_rule_is_rejected():
    with pytest.raises(ValueError):
        RuleDefinition.from_dict(
            {"id": "bad", "selector": {}, "requirements": [], "severity": "banana"}
        )
