from datetime import UTC, datetime

from crow_authority import DocumentAuthorityType
from crow_authority_discovery import ContractFramework, discover_authority
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
)


def document(doc_id: str, filename: str, doc_type: DocumentType) -> CrowDocument:
    return CrowDocument(
        id=doc_id,
        filename=filename,
        source_path=filename,
        fingerprint=DocumentFingerprint("hash-" + doc_id, 1, filename, None, None, 1, "meta"),
        metadata=DocumentMetadata(title=filename),
        document_type=doc_type,
        role=DocumentRole.PRIMARY,
        status=DocumentStatus.INDEXED,
        imported_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def page(doc_id: str, text: str) -> DocumentPage:
    return DocumentPage(
        "page-" + doc_id, doc_id, 1, 100, 100, 0, PageContentStatus.TEXT_AVAILABLE, text, "hash"
    )


def index(text: str) -> DocumentIndex:
    docs = (
        document("af", "AF.pdf", DocumentType.AF),
        document("desc", "Teknisk beskrivning.pdf", DocumentType.TECHNICAL_SPECIFICATION),
        document("draw", "Ritning.pdf", DocumentType.DRAWING),
    )
    pages = (page("af", text), page("desc", "Material: stål"), page("draw", "Material: plast"))
    return DocumentIndex(project_id="project", project_name="Project", documents=docs, pages=pages)


def test_discovers_ab04_and_document_types() -> None:
    result = discover_authority(index("Entreprenaden regleras av AB 04."))
    assert result.contract_framework == ContractFramework.AB04
    types = {item.document_id: item.authority_type for item in result.documents}
    assert types["af"] == DocumentAuthorityType.ADMINISTRATIVE_SPECIFICATIONS
    assert types["desc"] == DocumentAuthorityType.TECHNICAL_DESCRIPTION
    assert types["draw"] == DocumentAuthorityType.DRAWING


def test_discovers_afc111_drawing_override() -> None:
    result = discover_authority(index("AB 04. AFC.111 Ritningar gäller före beskrivningar."))
    assert result.framework.project_override is True
    assert result.framework.hierarchy.index(
        DocumentAuthorityType.DRAWING
    ) < result.framework.hierarchy.index(DocumentAuthorityType.TECHNICAL_DESCRIPTION)


def test_afc111_without_supported_phrase_requires_review() -> None:
    result = discover_authority(
        index("AB 04. AFC.111 Kontraktshandlingarna gäller i följande ordning.")
    )
    assert result.requires_review is True


def test_mixed_frameworks_require_review() -> None:
    result = discover_authority(index("AB 04 och ABT 06 omnämns."))
    assert result.contract_framework == ContractFramework.UNKNOWN
    assert result.requires_review is True
