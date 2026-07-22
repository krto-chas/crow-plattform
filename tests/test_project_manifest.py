import json
from pathlib import Path

from crow_project_manifest import ProjectManifestBuilder


def test_manifest_inventories_sources_and_historical_audits(tmp_path: Path) -> None:
    project = tmp_path / "project"
    uploads = tmp_path / "uploads"
    graph_dir = project / "building-graph"
    graph_dir.mkdir(parents=True)
    uploads.mkdir()
    (uploads / "drawing.dxf").write_text("0\nEOF\n", encoding="utf-8")
    (graph_dir / "graph.json").write_text(json.dumps({"objects": []}), encoding="utf-8")

    result = ProjectManifestBuilder().build(
        project_id="p1",
        project_version="0.7.0-alpha.1",
        project_directory=project,
        upload_directory=uploads,
        graph_audits=[
            {
                "audit_id": "a1",
                "graph_checksum": "historical",
                "created_at": "2026-07-20T00:00:00+00:00",
                "findings": [],
            }
        ],
        evidence_audits=[],
    ).to_dict()

    assert result["sources"][0]["imported_by"] == "crow_cad_text"
    assert result["graph_checksum"]
    assert result["audit_runs"]["graph"][0]["audit_id"] == "a1"
    assert result["validation"]["finding_count"] == 1
    assert result["validation"]["findings"][0]["code"] == "MANIFEST-AUDIT-002"
    assert result["metadata"]["read_only"] is True


def test_manifest_detects_duplicate_source_checksum_conflict(tmp_path: Path) -> None:
    project = tmp_path / "project"
    uploads = tmp_path / "uploads"
    (uploads / "one").mkdir(parents=True)
    (uploads / "two").mkdir(parents=True)
    (uploads / "one" / "same.pdf").write_bytes(b"one")
    (uploads / "two" / "same.pdf").write_bytes(b"two")

    result = ProjectManifestBuilder().build(
        project_id="p1",
        project_version="0.7.0-alpha.1",
        project_directory=project,
        upload_directory=uploads,
        graph_audits=[],
        evidence_audits=[],
    ).to_dict()

    codes = {item["code"] for item in result["validation"]["findings"]}
    assert "MANIFEST-SOURCE-001" in codes
    assert "MANIFEST-SOURCE-002" in codes
    assert result["validation"]["valid"] is False
