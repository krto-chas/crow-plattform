from datetime import UTC, datetime
from pathlib import Path

from crow_authority_discovery import discover_project
from crow_document_intelligence import (
    CrowDocument,
    DocumentFingerprint,
    DocumentIndex,
    DocumentMetadata,
    DocumentPage,
    DocumentRole,
    DocumentStatus,
    DocumentType,
    PageContentStatus,
    save_index,
)


def test_discover_project_writes_report_and_manifest(tmp_path: Path) -> None:
    doc = CrowDocument(
        id="af",
        filename="AF.pdf",
        source_path="AF.pdf",
        fingerprint=DocumentFingerprint("hash", 1, "af", None, None, 1, "meta"),
        metadata=DocumentMetadata(title="AF"),
        document_type=DocumentType.AF,
        role=DocumentRole.AUTHORITY,
        status=DocumentStatus.INDEXED,
        imported_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    page = DocumentPage(
        "page", "af", 1, 100, 100, 0, PageContentStatus.TEXT_AVAILABLE, "AB 04 gäller.", "hash"
    )
    project = tmp_path / "crow-project.json"
    save_index(
        DocumentIndex(project_id="p", project_name="P", documents=(doc,), pages=(page,)), project
    )
    result, report, manifest = discover_project(project)
    assert result.contract_framework.value == "ab04"
    assert report.exists()
    assert manifest.exists()
