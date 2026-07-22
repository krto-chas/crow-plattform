from pathlib import Path

from fastapi.testclient import TestClient

from crow_rule_explorer import RuleExplorerBuilder
from crow_workbench.app import create_app


def test_builds_rule_traceability_projection() -> None:
    result = RuleExplorerBuilder().build(
        rules=[
            {
                "rule_id": "VENT-EVID-001",
                "title": "Explicit feed relation",
                "description": "Requires explicit evidence.",
                "discipline": "VENT",
                "version": "0.1.0",
                "severity": "warning",
                "enabled": True,
                "evidence_required": True,
                "supports_auto_inference": False,
                "tags": ["evidence_gap"],
            }
        ],
        graph_audits=[
            {
                "audit_id": "vent:audit:1",
                "created_at": "2026-07-21T10:00:00+00:00",
                "graph_checksum": "abc",
                "findings": [
                    {
                        "finding_id": "f-1",
                        "rule_id": "VENT-EVID-001",
                        "rule_version": "0.1.0",
                        "severity": "warning",
                        "evidence_ids": ["ev-1"],
                    }
                ],
            }
        ],
        evidence_audits=[],
        graph_reviews=[
            {
                "audit_id": "vent:audit:1",
                "finding_id": "f-1",
                "decision": "acknowledge",
            }
        ],
        evidence_reviews=[],
        graph_verifications=[{"finding_id": "f-1"}],
        evidence_verifications=[],
    )

    rule = result["items"][0]
    assert result["summary"]["rules"] == 1
    assert rule["executions"] == 1
    assert rule["findings"] == 1
    assert rule["reviewed"] == 1
    assert rule["verified_resolutions"] == 1
    assert rule["runs"][0]["findings"][0]["evidence_ids"] == ["ev-1"]
    assert result["metadata"]["rule_configuration_mutated"] is False


def test_rule_explorer_endpoint_lists_installed_rules(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post(
        "/api/projects", json={"name": "Rule project", "project_id": "rule-project"}
    )

    response = client.get("/api/projects/rule-project/graph/rule-explorer")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["rules"] == 8
    assert payload["summary"]["active_rules"] == 8
    assert payload["metadata"]["read_only"] is True
    assert {item["rule_id"] for item in payload["items"]} >= {
        "VENT-EVID-001",
        "EVID-DQ-001",
    }
