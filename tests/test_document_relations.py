from pathlib import Path

from pypdf import PdfWriter

from crow_document_intelligence import create_project, import_into_project


def make_pdf(path: Path, pages: int = 1) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    with path.open("wb") as stream:
        writer.write(stream)


def test_authority_document_governs_primary_document(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", "Project")
    af = tmp_path / "AF-del.pdf"
    drawing = tmp_path / "V-57.1-100.pdf"
    make_pdf(af)
    make_pdf(drawing, pages=2)

    index, _ = import_into_project(project, [af, drawing])

    assert len(index.relations) == 1
    relation = index.relations[0]
    assert relation.relation_type == "governs"
    assert relation.confidence == 0.60
