import pytest

from crow_evidence_rules import EvidenceResolutionVerificationService


def test_evidence_resolution_verification_records_human_decision() -> None:
    result = EvidenceResolutionVerificationService().decide(
        base_audit_id="evidence:audit:base",
        target_audit_id="evidence:audit:target",
        finding_id="finding-1",
        lifecycle="no_longer_detected",
        previous_finding={"finding_id": "finding-1", "rule_id": "EVID-DQ-001"},
        decision="verify_resolved",
        reviewer="reviewer@example.test",
        rationale="Evidensreferensen har kontrollerats mot den nya grafen.",
        decided_at="2026-07-21T12:00:00+00:00",
    )

    assert result.decision == "verify_resolved"
    assert result.previous_finding["rule_id"] == "EVID-DQ-001"
    assert result.metadata == {
        "human_verification": True,
        "automatic_resolution_performed": False,
        "audit_runs_mutated": False,
        "graph_mutated": False,
        "evidence_mutated": False,
    }


def test_evidence_resolution_verification_rejects_persistent_finding() -> None:
    with pytest.raises(ValueError, match="inte längre upptäcks"):
        EvidenceResolutionVerificationService().decide(
            base_audit_id="evidence:audit:base",
            target_audit_id="evidence:audit:target",
            finding_id="finding-1",
            lifecycle="persistent",
            previous_finding={"finding_id": "finding-1"},
            decision="verify_resolved",
            reviewer="reviewer@example.test",
            rationale="Felaktigt försök.",
        )
