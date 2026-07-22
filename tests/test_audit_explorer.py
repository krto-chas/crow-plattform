from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_audit_explorer import AuditExplorerBuilder
from crow_workbench.app import create_app


def test_builds_combined_read_only_audit_projection() -> None:
    result = AuditExplorerBuilder().build(
        graph_audits=[
            {
                "audit_id": "vent:audit:1",
                "created_at": "2026-07-21T10:00:00+00:00",
                "graph_checksum": "abc",
                "metadata": {"rule_version": "0.1.0"},
                "summary": {"total": 2},
                "findings": [
                    {
                        "finding_id": "f-1",
                        "rule_id": "VENT-EVID-001",
                        "severity": "warning",
                    },
                    {
                        "finding_id": "f-2",
                        "rule_id": "VENT-DQ-001",
                        "severity": "error",
                    },
                ],
            }
        ],
        evidence_audits=[
            {
                "audit_id": "evidence:audit:1",
                "created_at": "2026-07-21T11:00:00+00:00",
                "graph_checksum": "def",
                "metadata": {"ruleset_version": "0.1.0"},
                "summary": {"total": 1},
                "findings": [
                    {
                        "finding_id": "e-1",
                        "rule_id": "EVID-EVID-001",
                        "severity": "info",
                    }
                ],
            }
        ],
        graph_reviews=[
            {
                "audit_id": "vent:audit:1",
                "finding_id": "f-1",
                "decision": "acknowledge",
            }
        ],
        evidence_reviews=[],
        graph_verifications=[{"finding_id": "old-finding"}],
        evidence_verifications=[],
    )

    assert result["summary"]["audit_runs"] == 2
    assert result["summary"]["findings"] == 3
    assert result["summary"]["reviewed_findings"] == 1
    assert result["summary"]["unreviewed_findings"] == 2
    assert result["summary"]["verified_resolutions"] == 1
    assert result["runs"][0]["domain"] == "evidence"
    graph_finding = result["domains"]["graph"]["runs"][0]["findings"][1]
    assert graph_finding["review_status"] == "reviewed"
    assert result["metadata"]["audit_runs_mutated"] is False


def test_rejects_duplicate_review_for_same_finding() -> None:
    audit = {
        "audit_id": "vent:audit:1",
        "metadata": {"rule_version": "0.1.0"},
        "findings": [{"finding_id": "f-1"}],
    }
    review = {"audit_id": "vent:audit:1", "finding_id": "f-1"}
    with pytest.raises(ValueError, match="Duplicate audit review"):
        AuditExplorerBuilder().build(
            graph_audits=[audit],
            evidence_audits=[],
            graph_reviews=[review, review],
            evidence_reviews=[],
            graph_verifications=[],
            evidence_verifications=[],
        )


def test_audit_explorer_endpoint_lists_persisted_domains(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post(
        "/api/projects", json={"name": "Audit project", "project_id": "audit-project"}
    )
    assert client.post("/api/projects/audit-project/graph/audit-runs").status_code == 201
    assert (
        client.post("/api/projects/audit-project/graph/evidence-audit-runs").status_code
        == 201
    )

    response = client.get("/api/projects/audit-project/graph/audit-explorer")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["audit_runs"] == 2
    assert payload["summary"]["graph_audit_runs"] == 1
    assert payload["summary"]["evidence_audit_runs"] == 1
    assert payload["metadata"]["read_only"] is True
