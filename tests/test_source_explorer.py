from pathlib import Path

from fastapi.testclient import TestClient

from crow_source_explorer import SourceExplorerBuilder
from crow_workbench.app import create_app


def test_builds_source_provenance_projection() -> None:
    result = SourceExplorerBuilder().build(
        {
            "project_id": "p-1",
            "project_version": "0.7.0-alpha.1",
            "graph_checksum": "abc",
            "canonical_model_version": "0.1",
            "graph_rule_engine_version": "0.1.0",
            "evidence_rules_version": "0.1.0",
            "sources": [
                {
                    "source_id": "a.ifc",
                    "relative_path": "a.ifc",
                    "type": "ifc",
                    "sha256": "1",
                    "size_bytes": 10,
                    "imported_by": "crow_ifc_relations",
                },
                {
                    "source_id": "b.bin",
                    "relative_path": "b.bin",
                    "type": "bin",
                    "sha256": "2",
                    "size_bytes": 5,
                    "imported_by": "unknown",
                },
            ],
            "audit_runs": {"graph": [{"audit_id": "g-1"}], "evidence": []},
            "validation": {
                "valid": True,
                "finding_count": 1,
                "findings": [
                    {
                        "code": "MANIFEST-SOURCE-003",
                        "severity": "warning",
                        "context": {"source_id": "b.bin"},
                    }
                ],
            },
        }
    )
    assert result["summary"]["sources"] == 2
    assert result["summary"]["size_bytes"] == 15
    assert result["summary"]["unknown_import_module"] == 1
    assert result["sources"][0]["type"] == "bin"
    assert result["sources"][0]["status"] == "attention_required"
    assert result["audit_inventory"]["total"] == 1
    assert result["metadata"]["automatic_import_performed"] is False


def test_source_explorer_endpoint_is_read_only(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/projects", json={"name": "Sources", "project_id": "sources"})
    response = client.get("/api/projects/sources/manifest/explorer")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["sources"] == 0
    assert payload["metadata"]["read_only"] is True
