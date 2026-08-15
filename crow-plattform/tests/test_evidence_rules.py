from __future__ import annotations

from crow_evidence_rules import EvidenceIntegrityAudit


def test_evidence_audit_reports_all_supported_integrity_findings() -> None:
    graph = {
        "evidence": [
            {"id": "ev-1", "kind": "dxf", "source_id": "a.dxf", "checksum": "a"},
            {"id": "ev-1", "kind": "dxf", "source_id": "a.dxf", "checksum": "a"},
            {"id": "ev-2", "kind": "dxf", "source_id": "same.dxf", "checksum": "b"},
            {"id": "ev-3", "kind": "dxf", "source_id": "same.dxf", "checksum": "c"},
        ],
        "objects": [{"id": "obj-1", "evidence_ids": ["ev-missing"]}],
        "relations": [],
        "properties": [],
    }

    result = EvidenceIntegrityAudit().audit(graph)

    assert result.summary == {"total": 6, "data_quality": 3, "evidence_gap": 3}
    assert {finding.rule_id for finding in result.findings} == {
        "EVID-DQ-001",
        "EVID-DQ-002",
        "EVID-DQ-003",
        "EVID-EVID-001",
    }
    assert result.metadata["automatic_repair_performed"] is False
    assert result.metadata["graph_mutated"] is False
    assert result.metadata["evidence_mutated"] is False


def test_unreferenced_evidence_is_not_asserted_as_technical_defect() -> None:
    result = EvidenceIntegrityAudit().audit(
        {"evidence": [{"id": "ev-1"}], "objects": [], "relations": [], "properties": []}
    )

    finding = result.findings[0]
    assert finding.rule_id == "EVID-EVID-001"
    assert finding.status == "review_required"
    assert finding.metadata["technical_defect_asserted"] is False
