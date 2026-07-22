import pytest

from crow_evidence_rules import EvidenceAuditDiffer


def _audit(audit_id: str, finding_ids: list[str]) -> dict[str, object]:
    return {
        "audit_id": audit_id,
        "findings": [
            {"finding_id": finding_id, "rule_id": "EVID-DQ-001"}
            for finding_id in finding_ids
        ],
    }


def test_evidence_audit_diff_classifies_lifecycle() -> None:
    result = EvidenceAuditDiffer().compare(
        _audit("evidence:audit:base", ["f1", "f2"]),
        _audit("evidence:audit:target", ["f2", "f3"]),
    )

    assert result.summary == {
        "total": 3,
        "new": 1,
        "persistent": 1,
        "no_longer_detected": 1,
    }
    assert {item.finding_id: item.lifecycle for item in result.changes} == {
        "f1": "no_longer_detected",
        "f2": "persistent",
        "f3": "new",
    }
    candidate = next(item for item in result.changes if item.finding_id == "f1")
    assert candidate.metadata["resolution_status"] == "candidate_for_verification"
    assert candidate.metadata["automatic_resolution_asserted"] is False
    assert result.metadata["evidence_mutated"] is False


def test_evidence_audit_diff_rejects_same_audit() -> None:
    with pytest.raises(ValueError, match="Samma evidensgranskning"):
        EvidenceAuditDiffer().compare(_audit("same", []), _audit("same", []))


def test_evidence_audit_diff_rejects_duplicate_findings() -> None:
    duplicate = {
        "audit_id": "evidence:audit:duplicate",
        "findings": [{"finding_id": "f1"}, {"finding_id": "f1"}],
    }
    with pytest.raises(ValueError, match="Duplicerat finding_id"):
        EvidenceAuditDiffer().compare(duplicate, _audit("target", []))
