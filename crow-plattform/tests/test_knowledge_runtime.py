import json
from pathlib import Path

from crow_knowledge_runtime import KnowledgePackRuntime

ROOT = Path(__file__).resolve().parents[1] / "knowledge"


def test_discovers_and_validates_crow_vent() -> None:
    registry = KnowledgePackRuntime(ROOT).registry()
    assert registry["pack_count"] >= 1
    vent = next(pack for pack in registry["packs"] if pack["id"] == "crow.vent")
    assert vent["status"] == "active"
    assert vent["rule_count"] == 1
    assert vent["ontology_class_count"] == 5


def test_exposes_rules_for_runtime_execution() -> None:
    rules = KnowledgePackRuntime(ROOT).rules("crow.vent")
    assert rules[0]["id"] == "vent.component.must_belong_to_system"


def test_rejects_ontology_cycle(tmp_path: Path) -> None:
    pack = tmp_path / "bad"
    pack.mkdir()
    (pack / "manifest.json").write_text(
        json.dumps({"id": "bad", "name": "Bad", "version": "1.0.0", "ontology": "ontology.json"})
    )
    (pack / "ontology.json").write_text(
        json.dumps({"classes": [{"id": "A", "parent": "B"}, {"id": "B", "parent": "A"}]})
    )
    runtime = KnowledgePackRuntime(tmp_path)
    loaded = runtime.load(pack)
    validation = runtime.validate(loaded)
    assert not validation.valid
    assert any("Cykel" in error for error in validation.errors)


def test_rejects_missing_dependency(tmp_path: Path) -> None:
    pack = tmp_path / "bad-dep"
    pack.mkdir()
    (pack / "manifest.json").write_text(
        json.dumps(
            {
                "id": "bad.dep",
                "name": "Bad dependency",
                "version": "1.0.0",
                "requires": ["crow.fire>=1.0"],
            }
        )
    )
    validation = KnowledgePackRuntime(tmp_path).validate(KnowledgePackRuntime(tmp_path).load(pack))
    assert not validation.valid
    assert "Beroende saknas: crow.fire" in validation.errors
