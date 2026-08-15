from pathlib import Path

from pypdf import PdfWriter

from crow_document_intelligence import (
    DocumentRole,
    DocumentStatus,
    DocumentType,
    create_project,
    import_into_project,
    load_index,
    summarize,
)


def make_pdf(path: Path, pages: int = 1) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    with path.open("wb") as stream:
        writer.write(stream)


def test_import(tmp_path: Path) -> None:
    project = create_project(tmp_path / "demo", "Demo")
    pdf = tmp_path / "V-57.1-100.pdf"
    make_pdf(pdf, 2)
    index, _ = import_into_project(project, [pdf])
    doc = index.documents[0]
    assert doc.document_type == DocumentType.DRAWING
    assert doc.role == DocumentRole.PRIMARY
    assert doc.fingerprint.page_count == 2
    assert doc.status == DocumentStatus.INDEXED


def test_duplicate(tmp_path: Path) -> None:
    project = create_project(tmp_path / "demo", "Demo")
    pdf = tmp_path / "V-57.1-100.pdf"
    make_pdf(pdf)
    import_into_project(project, [pdf])
    index, session = import_into_project(project, [pdf])
    assert len(index.documents) == 1
    assert session.results[0].outcome.value == "duplicate"


def test_revision(tmp_path: Path) -> None:
    project = create_project(tmp_path / "demo", "Demo")
    a = tmp_path / "V-57.1-100 Rev A.pdf"
    b = tmp_path / "V-57.1-100 Rev B.pdf"
    make_pdf(a, 1)
    make_pdf(b, 2)
    import_into_project(project, [a])
    index, session = import_into_project(project, [b])
    assert index.documents[0].status == DocumentStatus.SUPERSEDED
    assert index.documents[1].supersedes_document_id == index.documents[0].id
    assert session.results[0].outcome.value == "revision"


def test_roundtrip(tmp_path: Path) -> None:
    project = create_project(tmp_path / "demo", "Demo")
    pdf = tmp_path / "AF-del.pdf"
    make_pdf(pdf)
    import_into_project(project, [pdf])
    result = summarize(load_index(project))
    assert result["types"] == {"af": 1}
    assert result["roles"] == {"authority": 1}
