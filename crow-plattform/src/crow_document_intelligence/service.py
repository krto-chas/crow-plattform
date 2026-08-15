from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import TypedDict

from .intake import collect_pdf_paths, import_documents
from .models import DocumentIndex, ImportSession
from .repository import load_index, save_index


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "project"


def create_project(
    directory: Path,
    name: str,
    project_id: str | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / "crow-project.json"
    save_index(
        DocumentIndex(
            project_id=project_id or slugify(name),
            project_name=name,
        ),
        path,
    )
    return path


def import_into_project(
    project_file: Path,
    inputs: list[Path],
    recursive: bool = False,
) -> tuple[DocumentIndex, ImportSession]:
    index = load_index(project_file)
    paths = collect_pdf_paths(inputs, recursive)
    updated, session = import_documents(index, paths)
    save_index(updated, project_file)
    return updated, session


class ProjectSummary(TypedDict):
    project_id: str
    project_name: str
    documents_total: int
    documents_active: int
    superseded: int
    import_sessions: int
    failed_imports: int
    relations: int
    pages: int
    regions: int
    pages_requiring_ocr: int
    extracted_characters: int
    types: dict[str, int]
    roles: dict[str, int]


def summarize(index: DocumentIndex) -> ProjectSummary:
    active = index.active_documents
    return {
        "project_id": index.project_id,
        "project_name": index.project_name,
        "documents_total": len(index.documents),
        "documents_active": len(active),
        "superseded": len(index.documents) - len(active),
        "import_sessions": len(index.import_sessions),
        "failed_imports": sum(session.failed_count for session in index.import_sessions),
        "relations": len(index.relations),
        "pages": len(index.pages),
        "regions": len(index.regions),
        "pages_requiring_ocr": sum(
            page.content_status.value == "ocr_required" for page in index.pages
        ),
        "extracted_characters": sum(len(page.text) for page in index.pages),
        "types": dict(sorted(Counter(document.document_type.value for document in active).items())),
        "roles": dict(sorted(Counter(document.role.value for document in active).items())),
    }
