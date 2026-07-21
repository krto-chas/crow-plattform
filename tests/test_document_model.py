from pathlib import Path

import pytest
from pypdf import PdfWriter

from crow_document_intelligence import (
    BoundingBox,
    PageContentStatus,
    create_project,
    import_into_project,
    load_index,
    summarize,
)


def make_pdf(path: Path, pages: int = 2) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with path.open("wb") as stream:
        writer.write(stream)


def test_import_creates_stable_pages_and_regions(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", "Project")
    pdf = tmp_path / "V-57.1-100.pdf"
    make_pdf(pdf)

    index, _ = import_into_project(project, [pdf])
    loaded = load_index(project)

    assert len(index.pages) == 2
    assert len(index.regions) == 2
    assert loaded.pages[0].locator.endswith("#page=1")
    assert loaded.regions[0].locator.endswith("xywh=0.000000,0.000000,1.000000,1.000000")
    assert loaded.pages[0].content_status == PageContentStatus.OCR_REQUIRED


def test_summary_reports_document_structure(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", "Project")
    pdf = tmp_path / "V-57.1-100.pdf"
    make_pdf(pdf, pages=3)
    index, _ = import_into_project(project, [pdf])

    result = summarize(index)

    assert result["pages"] == 3
    assert result["regions"] == 3
    assert result["pages_requiring_ocr"] == 3


def test_bounding_box_rejects_coordinates_outside_page() -> None:
    with pytest.raises(ValueError):
        BoundingBox(x=0.8, y=0.0, width=0.3, height=1.0)
