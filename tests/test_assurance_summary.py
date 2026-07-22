from __future__ import annotations

import pytest

from crow_assurance import ProjectAssuranceSummaryBuilder


def _audit(audit_id: str, created_at: str, findings: list[dict[str, str]]) -> dict[str, object]:
    return {
        "audit_id": audit_id,
        "created_at": created_at,
        "graph_checksum": f"checksum-{audit_id}",
        "findings": findings,
    }


def test_summary_uses_latest_audits_and_counts_review_state() -> None:
    older = _audit("vent:audit:old", "2026-07-20T10:00:00+00:00", [])
    latest = _audit(
        "vent:audit:new",
        "2026-07-21T10:00:00+00:00",
        [
            {"finding_id": "f-1", "severity": "error", "category": "data_quality"},
            {"finding_id": "f-2", "severity": "warning", "category": "evidence_gap"},
        ],
    )
    evidence = _audit("evidence:audit:1", "2026-07-21T09:00:00+00:00", [])

    result = ProjectAssuranceSummaryBuilder().build(
        project_id="demo",
        graph_audits=[latest, older],
        evidence_audits=[evidence],
        graph_reviews=[{"audit_id": "vent:audit:new", "finding_id": "f-1"}],
    )

    assert result.status == "attention_required"
    assert result.graph.audit_id == "vent:audit:new"
    assert result.graph.reviewed_count == 1
    assert result.graph.unreviewed_count == 1
    assert result.graph.severity_counts == {"error": 1, "warning": 1}
    assert result.evidence.status == "no_findings_detected"
    assert result.metadata["technical_correctness_asserted"] is False


def test_summary_reports_incomplete_coverage_without_persisted_audits() -> None:
    result = ProjectAssuranceSummaryBuilder().build(
        project_id="demo",
        graph_audits=[],
        evidence_audits=[],
    )

    assert result.status == "incomplete_audit_coverage"
    assert result.graph.status == "no_persisted_audit"
    assert result.evidence.status == "no_persisted_audit"


def test_summary_counts_verified_resolutions_for_latest_target() -> None:
    graph = _audit("vent:audit:target", "2026-07-21T10:00:00+00:00", [])
    result = ProjectAssuranceSummaryBuilder().build(
        project_id="demo",
        graph_audits=[graph],
        evidence_audits=[],
        graph_verifications=[
            {"target_audit_id": "vent:audit:target", "decision": "verify_resolved"},
            {"target_audit_id": "vent:audit:target", "decision": "reject_resolution"},
        ],
    )

    assert result.graph.verified_resolution_count == 1


def test_summary_rejects_duplicate_finding_ids() -> None:
    graph = _audit(
        "vent:audit:1",
        "2026-07-21T10:00:00+00:00",
        [
            {"finding_id": "f-1"},
            {"finding_id": "f-1"},
        ],
    )
    with pytest.raises(ValueError, match="dubblerat finding_id"):
        ProjectAssuranceSummaryBuilder().build(
            project_id="demo",
            graph_audits=[graph],
            evidence_audits=[],
        )
