import json
from pathlib import Path

from crow_document_intelligence.repository import _heal_document_path


def make_tree(tmp_path: Path) -> tuple[Path, Path]:
    project_file = tmp_path / "projects" / "mandelblomman" / "crow-project.json"
    project_file.parent.mkdir(parents=True)
    project_file.write_text(json.dumps({"documents": []}))
    upload = tmp_path / "uploads" / "mandelblomman" / "ritning.pdf"
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b"%PDF-1.4")
    return project_file, upload


def test_stale_absolute_path_is_remapped_after_rename(tmp_path: Path) -> None:
    project_file, upload = make_tree(tmp_path)
    stale = "C:/Users/x/Desktop/CROW Plattform/data/uploads/mandelblomman/ritning.pdf"
    healed = _heal_document_path(stale, project_file)
    assert Path(healed) == upload.resolve()


def test_existing_absolute_path_is_kept(tmp_path: Path) -> None:
    project_file, upload = make_tree(tmp_path)
    healed = _heal_document_path(str(upload), project_file)
    assert Path(healed).resolve() == upload.resolve()


def test_relative_path_resolves_against_data_root(tmp_path: Path) -> None:
    project_file, upload = make_tree(tmp_path)
    healed = _heal_document_path("uploads/mandelblomman/ritning.pdf", project_file)
    assert Path(healed) == upload.resolve()


def test_unresolvable_path_is_left_untouched(tmp_path: Path) -> None:
    project_file, _ = make_tree(tmp_path)
    stale = "/gone/away/annan.pdf"
    assert _heal_document_path(stale, project_file) == stale
