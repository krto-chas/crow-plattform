from pathlib import Path

from pypdf import PdfWriter

from crow_module_conformance.cli import main


def test_cli(tmp_path: Path) -> None:
    directory = tmp_path / "project"
    assert main(["project", "create", str(directory), "--name", "Test"]) == 0
    pdf = tmp_path / "V-57.1-100.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with pdf.open("wb") as stream:
        writer.write(stream)
    project = directory / "crow-project.json"
    assert main(["project", "import", str(project), str(pdf)]) == 0
    assert main(["project", "show", str(project), "--json"]) == 0
