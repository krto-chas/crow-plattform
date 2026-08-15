from pathlib import Path

import pytest
from pypdf import PdfWriter

from crow_canonical import CanonicalEvidence, CanonicalObject, CanonicalObjectType
from crow_pdf_evidence import (
    PdfCanonicalEvidenceLinker,
    PdfEvidenceExtraction,
    PdfEvidenceExtractor,
    PdfPageEvidence,
)


def _object(canonical_id: str, name: str) -> CanonicalObject:
    return CanonicalObject(
        canonical_id=canonical_id,
        object_type=CanonicalObjectType.AIR_TERMINAL,
        discipline="ventilation",
        name=name,
        confidence=1.0,
        properties={},
        evidence=CanonicalEvidence(
            source_id="drawing.dxf",
            source_kind="drawing_text",
            locator="A1",
            confidence=1.0,
        ),
    )


def test_links_only_exact_boundary_aware_object_names() -> None:
    extraction = PdfEvidenceExtraction(
        schema_version="crow-pdf-evidence-v0.1",
        source_id="description.pdf",
        source_sha256="a" * 64,
        page_count=2,
        text_page_count=2,
        ocr_required_page_count=0,
        pages=(
            PdfPageEvidence(1, "Montera TD1 och TD10.", "b" * 64, "text_available"),
            PdfPageEvidence(2, "Kontroll av TD1.", "c" * 64, "text_available"),
        ),
        warnings=(),
    )
    result = PdfCanonicalEvidenceLinker().link(
        extraction,
        [_object("ccm:1", "TD1"), _object("ccm:2", "FD2")],
    )
    assert len(result.links) == 2
    assert {link.page_number for link in result.links} == {1, 2}
    assert all(link.match_method == "exact_name_boundary" for link in result.links)
    assert result.unmatched_object_ids == ("ccm:2",)
    assert result.to_dict()["semantic_inference_performed"] is False


def test_extracts_pdf_pages_and_marks_empty_page_for_ocr(tmp_path: Path) -> None:
    path = tmp_path / "empty.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as stream:
        writer.write(stream)
    result = PdfEvidenceExtractor().extract_path(path)
    assert result.page_count == 1
    assert result.text_page_count == 0
    assert result.ocr_required_page_count == 1
    assert result.pages[0].extraction_status == "ocr_required"
    assert "explicit OCR" in result.warnings[0]


def test_rejects_non_pdf_sources(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    path.write_text("TD1")
    with pytest.raises(ValueError, match="Unsupported PDF evidence source format"):
        PdfEvidenceExtractor().extract_path(path)
