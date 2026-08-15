import pytest

from crow_vent import VentResolutionVerificationService


def test_resolution_verification_records_human_decision_without_mutation() -> None:
    result = VentResolutionVerificationService().decide(
        base_audit_id="vent:audit:base",
        target_audit_id="vent:audit:target",
        finding_id="finding-1",
        lifecycle="no_longer_detected",
        previous_finding={"finding_id": "finding-1", "rule_id": "VENT-EVID-001"},
        decision="verify_resolved",
        reviewer="reviewer@example.test",
        rationale="Relationen har verifierats i den uppdaterade grafen.",
        decided_at="2026-07-21T10:30:00+00:00",
    )

    assert result.decision == "verify_resolved"
    assert result.previous_finding["rule_id"] == "VENT-EVID-001"
    assert result.metadata == {
        "human_verification": True,
        "automatic_resolution_performed": False,
        "audit_runs_mutated": False,
        "graph_mutated": False,
    }


def test_resolution_verification_rejects_persistent_finding() -> None:
    with pytest.raises(ValueError, match="inte längre upptäcks"):
        VentResolutionVerificationService().decide(
            base_audit_id="vent:audit:base",
            target_audit_id="vent:audit:target",
            finding_id="finding-1",
            lifecycle="persistent",
            previous_finding={"finding_id": "finding-1"},
            decision="verify_resolved",
            reviewer="reviewer@example.test",
            rationale="Felaktigt försök.",
        )
