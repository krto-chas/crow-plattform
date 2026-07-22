import pytest

from crow_vent import VentAuditDiffer


def _audit(audit_id: str, finding_ids: list[str]) -> dict[str, object]:
    return {
        "audit_id": audit_id,
        "findings": [
            {"finding_id": finding_id, "rule_id": "VENT-EVID-001"}
            for finding_id in finding_ids
        ],
    }


def test_audit_diff_classifies_new_persistent_and_no_longer_detected() -> None:
    result = VentAuditDiffer().compare(
        _audit("vent:audit:base", ["f1", "f2"]),
        _audit("vent:audit:target", ["f2", "f3"]),
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
    resolved_candidate = next(item for item in result.changes if item.finding_id == "f1")
    assert resolved_candidate.metadata["resolution_status"] == "candidate_for_verification"
    assert resolved_candidate.metadata["automatic_resolution_asserted"] is False


def test_audit_diff_carries_base_review_without_changing_lifecycle() -> None:
    reviews = [
        {
            "audit_id": "vent:audit:base",
            "finding_id": "f1",
            "review_id": "review-1",
            "decision": "acknowledge",
            "reviewer": "reviewer@example.test",
            "decided_at": "2026-07-21T10:00:00+00:00",
        }
    ]

    result = VentAuditDiffer().compare(
        _audit("vent:audit:base", ["f1"]),
        _audit("vent:audit:target", []),
        reviews=reviews,
    )

    change = result.changes[0]
    assert change.lifecycle == "no_longer_detected"
    assert change.metadata["base_review"]["decision"] == "acknowledge"
    assert result.metadata["automatic_resolution_performed"] is False


def test_audit_diff_rejects_same_audit() -> None:
    with pytest.raises(ValueError, match="Samma granskningskörning"):
        VentAuditDiffer().compare(_audit("same", []), _audit("same", []))
