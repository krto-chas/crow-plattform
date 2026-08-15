from pathlib import Path

from pypdf import PdfReader, PdfWriter

from crow_document_intelligence import PageContentStatus
from crow_document_intelligence.extraction import extract_pdf_structure


def test_empty_vector_page_is_marked_for_ocr(tmp_path: Path) -> None:
    path = tmp_path / "empty.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=200)
    with path.open("wb") as stream:
        writer.write(stream)

    pages, regions = extract_pdf_structure(path, "doc:test")

    assert len(PdfReader(path).pages) == 1
    assert pages[0].content_status == PageContentStatus.OCR_REQUIRED
    assert pages[0].width_points == 100.0
    assert pages[0].height_points == 200.0
    assert regions[0].page_id == pages[0].id
