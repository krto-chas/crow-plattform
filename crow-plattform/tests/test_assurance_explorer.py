from pathlib import Path

from fastapi.testclient import TestClient

from crow_assurance_explorer import AssuranceExplorerBuilder
from crow_workbench.app import create_app


def test_builds_action_queue_from_unreviewed_latest_findings() -> None:
    summary = {
        "status": "attention_required",
        "domains": {
            "graph": {"audit_id": "g-1", "status": "attention_required"},
            "evidence": {"audit_id": None, "status": "no_persisted_audit"},
        },
        "totals": {"findings": 2, "reviewed": 1, "unreviewed": 1, "verified_resolutions": 0},
    }
    result = AssuranceExplorerBuilder().build(
        assurance_summary=summary,
        graph_audits=[
            {
                "audit_id": "g-1",
                "created_at": "2026-07-21T10:00:00+00:00",
                "findings": [
                    {"finding_id": "f-1", "rule_id": "R-1", "severity": "warning"},
                    {"finding_id": "f-2", "rule_id": "R-2", "severity": "error"},
                ],
            }
        ],
        evidence_audits=[],
        graph_reviews=[{"audit_id": "g-1", "finding_id": "f-1"}],
        evidence_reviews=[],
    )

    assert result["coverage"]["complete"] is False
    assert result["summary"]["actions"] == 1
    assert result["action_queue"][0]["finding_id"] == "f-2"
    assert result["metadata"]["automatic_approval_performed"] is False


def test_assurance_explorer_endpoint_is_read_only(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post(
        "/api/projects", json={"name": "Assurance project", "project_id": "assurance-project"}
    )

    response = client.get("/api/projects/assurance-project/graph/assurance-explorer")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "incomplete_audit_coverage"
    assert payload["coverage"]["complete"] is False
    assert payload["metadata"]["read_only"] is True
