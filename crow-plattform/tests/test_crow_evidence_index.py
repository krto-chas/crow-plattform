import pytest

from crow_evidence_index import EvidenceIndexBuilder


def test_indexes_references_and_reports_missing_and_unreferenced_evidence() -> None:
    graph = {
        "evidence": [
            {
                "id": "ev-1",
                "kind": "dxf",
                "source_id": "drawing.dxf",
                "locator": "A1",
                "checksum": "a" * 64,
                "confidence": 1.0,
            },
            {
                "id": "ev-2",
                "kind": "pdf",
                "source_id": "description.pdf",
                "locator": "page:1",
                "checksum": "b" * 64,
                "confidence": 1.0,
            },
        ],
        "objects": [{"id": "obj-1", "evidence_ids": ["ev-1", "ev-missing"]}],
        "relations": [{"id": "rel-1", "evidence_ids": ["ev-1"]}],
        "properties": [],
    }

    result = EvidenceIndexBuilder().build(graph)

    assert result.evidence_count == 2
    assert result.reference_count == 3
    assert result.missing_evidence_ids == ("ev-missing",)
    assert result.unreferenced_evidence_ids == ("ev-2",)
    assert result.entries[0].reference_count == 2
    payload = result.to_dict()
    assert payload["graph_mutated"] is False
    assert payload["inference_performed"] is False


def test_reports_duplicate_ids_and_source_checksum_conflicts() -> None:
    graph = {
        "evidence": [
            {"id": "ev-1", "kind": "ifc", "source_id": "model.ifc", "checksum": "a" * 64},
            {"id": "ev-1", "kind": "ifc", "source_id": "model.ifc", "checksum": "a" * 64},
            {"id": "ev-2", "kind": "ifc", "source_id": "model.ifc", "checksum": "b" * 64},
        ],
        "objects": [],
        "relations": [],
        "properties": [],
    }

    result = EvidenceIndexBuilder().build(graph)

    assert result.duplicate_evidence_ids == ("ev-1",)
    assert len(result.source_checksum_conflicts) == 1
    conflict = result.source_checksum_conflicts[0]
    assert conflict.source_id == "model.ifc"
    assert conflict.checksums == ("a" * 64, "b" * 64)
    assert conflict.evidence_ids == ("ev-1", "ev-2")


def test_rejects_invalid_evidence_references() -> None:
    with pytest.raises(ValueError, match="evidence_ids must be a list or tuple"):
        EvidenceIndexBuilder().build(
            {
                "evidence": [],
                "objects": [{"id": "obj-1", "evidence_ids": "ev-1"}],
                "relations": [],
                "properties": [],
            }
        )
