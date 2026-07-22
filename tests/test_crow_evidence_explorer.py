import pytest

from crow_evidence_explorer import EvidenceExplorerBuilder


def test_builds_evidence_centric_projection() -> None:
    graph = {
        "evidence": [
            {"id": "ev-1", "kind": "dxf", "source_id": "a.dxf", "locator": "A1"},
            {"id": "ev-2", "kind": "pdf", "source_id": "b.pdf", "locator": "page:1"},
        ],
        "objects": [{"id": "obj-1", "name": "TD1", "evidence_ids": ["ev-1"]}],
        "relations": [{"id": "rel-1", "relation_type": "feeds", "evidence_ids": ["ev-1"]}],
        "properties": [{"id": "prop-1", "name": "flow", "evidence_ids": ["missing"]}],
    }
    result = EvidenceExplorerBuilder().build(graph)
    assert result["summary"] == {
        "evidence": 2,
        "referenced": 1,
        "unreferenced": 1,
        "references": 2,
        "missing_references": 1,
        "duplicate_evidence_ids": 0,
    }
    assert result["items"][0]["reference_count"] == 2
    assert result["items"][1]["status"] == "unreferenced"
    assert result["metadata"]["graph_mutated"] is False


def test_rejects_invalid_reference_collection() -> None:
    with pytest.raises(ValueError, match="evidence_ids must be a list"):
        EvidenceExplorerBuilder().build(
            {
                "evidence": [],
                "objects": [{"id": "o", "evidence_ids": "ev"}],
                "relations": [],
                "properties": [],
            }
        )
