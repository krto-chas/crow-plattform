from pathlib import Path

import pytest

from crow_building_graph.models import CrowObject, CrowRelation
from crow_building_graph.repository import GraphRepository
from crow_inference import InferenceService


def prepared(tmp_path: Path) -> tuple[InferenceService, str]:
    repo = GraphRepository(tmp_path / "graph.json")
    for object_id in ("terminal", "system", "ahu"):
        repo.add("objects", CrowObject(id=object_id, object_type="component"))
    repo.add(
        "relations",
        CrowRelation(id="r1", source_id="terminal", relation_type="served_by", target_id="system"),
    )
    repo.add(
        "relations",
        CrowRelation(id="r2", source_id="system", relation_type="served_by", target_id="ahu"),
    )
    service = InferenceService(tmp_path / "graph.json")
    result = service.run()
    relation_id = next(
        item["id"] for item in result["derived_relations"] if item["source_id"] == "terminal"
    )
    return service, relation_id


def test_review_acceptance_is_persisted(tmp_path: Path) -> None:
    service, relation_id = prepared(tmp_path)
    review = service.review_relation(
        relation_id, decision="accepted", actor="reviewer", note="verified"
    )
    assert review["status"] == "accepted"
    assert service.reviews()["summary"]["accepted"] == 1


def test_rejected_relation_cannot_be_promoted(tmp_path: Path) -> None:
    service, relation_id = prepared(tmp_path)
    service.review_relation(relation_id, decision="rejected")
    with pytest.raises(ValueError, match="accepterad"):
        service.promote_relation(relation_id)


def test_accepted_relation_can_be_promoted(tmp_path: Path) -> None:
    service, relation_id = prepared(tmp_path)
    service.review_relation(relation_id, decision="accepted", actor="reviewer")
    promoted = service.promote_relation(relation_id, actor="reviewer")
    relation = promoted["relation"]
    assert relation["relation_type"] == "indirectly_served_by"
    assert relation["metadata"]["promoted_from_inference"] == relation_id
    assert service.status()["status"] == "stale"


def test_promoted_review_cannot_be_changed(tmp_path: Path) -> None:
    service, relation_id = prepared(tmp_path)
    service.review_relation(relation_id, decision="accepted")
    service.promote_relation(relation_id)
    with pytest.raises(ValueError, match="omprövas"):
        service.review_relation(relation_id, decision="rejected")


def test_review_filter(tmp_path: Path) -> None:
    service, relation_id = prepared(tmp_path)
    service.review_relation(relation_id, decision="accepted")
    assert service.reviews(status="accepted")["count"] == 1
    assert service.reviews(status="rejected")["count"] == 0
