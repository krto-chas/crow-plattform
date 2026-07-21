from pathlib import Path

from pypdf import PdfWriter

from crow_document_intelligence import (
    ImportOutcome,
    ImportSessionStatus,
    create_project,
    import_into_project,
    load_index,
)


def make_pdf(path: Path, pages: int = 1) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    with path.open("wb") as stream:
        writer.write(stream)


def test_import_session_is_persisted(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", "Project")
    drawing = tmp_path / "V-57.1-100.pdf"
    make_pdf(drawing)

    _, session = import_into_project(project, [drawing])
    loaded = load_index(project)

    assert session.status == ImportSessionStatus.COMPLETED
    assert session.imported_count == 1
    assert loaded.import_sessions[-1].id == session.id
    assert loaded.documents[0].import_session_id == session.id


def test_batch_continues_after_invalid_pdf(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", "Project")
    valid = tmp_path / "V-57.1-100.pdf"
    invalid = tmp_path / "broken.pdf"
    make_pdf(valid)
    invalid.write_text("not a pdf", encoding="utf-8")

    index, session = import_into_project(project, [valid, invalid])

    assert len(index.documents) == 1
    assert session.status == ImportSessionStatus.COMPLETED_WITH_ERRORS
    assert session.failed_count == 1
    assert {result.outcome for result in session.results} == {
        ImportOutcome.IMPORTED,
        ImportOutcome.FAILED,
    }


def test_repeated_batch_is_idempotent(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project", "Project")
    drawing = tmp_path / "V-57.1-100.pdf"
    make_pdf(drawing)

    import_into_project(project, [drawing])
    index, session = import_into_project(project, [drawing])

    assert len(index.documents) == 1
    assert session.results[0].outcome == ImportOutcome.DUPLICATE
