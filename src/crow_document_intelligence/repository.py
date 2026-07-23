from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .document_model import (
    BoundingBox,
    DocumentPage,
    DocumentRegion,
    PageContentStatus,
    RegionKind,
)
from .models import (
    CrowDocument,
    DocumentFingerprint,
    DocumentIndex,
    DocumentMetadata,
    DocumentRelation,
    DocumentRole,
    DocumentStatus,
    DocumentType,
    ImportItemResult,
    ImportOutcome,
    ImportSession,
    ImportSessionStatus,
)


def _default(value: object) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def save_index(index: DocumentIndex, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            asdict(index),
            default=_default,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _load_document(item: dict[str, Any]) -> CrowDocument:
    return CrowDocument(
        id=item["id"],
        filename=item["filename"],
        source_path=item["source_path"],
        fingerprint=DocumentFingerprint(**item["fingerprint"]),
        metadata=DocumentMetadata(**item["metadata"]),
        document_type=DocumentType(item["document_type"]),
        role=DocumentRole(item["role"]),
        status=DocumentStatus(item["status"]),
        imported_at=datetime.fromisoformat(item["imported_at"]),
        supersedes_document_id=item.get("supersedes_document_id"),
        import_session_id=item.get("import_session_id"),
    )


def _load_session(item: dict[str, Any]) -> ImportSession:
    results = tuple(
        ImportItemResult(
            path=result["path"],
            outcome=ImportOutcome(result["outcome"]),
            document_id=result.get("document_id"),
            related_document_id=result.get("related_document_id"),
            message=result.get("message", ""),
            error_type=result.get("error_type"),
        )
        for result in item.get("results", [])
    )
    return ImportSession(
        id=item["id"],
        started_at=datetime.fromisoformat(item["started_at"]),
        completed_at=(
            datetime.fromisoformat(item["completed_at"]) if item.get("completed_at") else None
        ),
        status=ImportSessionStatus(item["status"]),
        requested_paths=tuple(item.get("requested_paths", [])),
        results=results,
    )


def _load_page(item: dict[str, Any]) -> DocumentPage:
    return DocumentPage(
        id=item["id"],
        document_id=item["document_id"],
        page_number=item["page_number"],
        width_points=item["width_points"],
        height_points=item["height_points"],
        rotation_degrees=item["rotation_degrees"],
        content_status=PageContentStatus(item["content_status"]),
        text=item["text"],
        text_sha256=item["text_sha256"],
    )


def _load_region(item: dict[str, Any]) -> DocumentRegion:
    return DocumentRegion(
        id=item["id"],
        document_id=item["document_id"],
        page_id=item["page_id"],
        page_number=item["page_number"],
        kind=RegionKind(item["kind"]),
        bounds=BoundingBox(**item["bounds"]),
        text=item.get("text"),
        confidence=item.get("confidence", 1.0),
        extraction_method=item.get("extraction_method", "embedded_pdf_text"),
    )


def _heal_document_path(document_path: str, project_file: Path) -> str:
    """Resolve stored document paths against the current tree.

    Paths are stored absolute at import time, which breaks when the data
    root is renamed or moved. Healing: a relative path resolves against
    the data root; a stale absolute path is remapped to the project's
    upload directory when a file with the same name exists there. The
    original string is kept whenever no better candidate exists.
    """
    from pathlib import PurePosixPath, PureWindowsPath

    stored = Path(document_path)
    parents = project_file.parents
    data_root = parents[2] if len(parents) > 2 else project_file.parent
    is_absolute = PurePosixPath(document_path).is_absolute() or PureWindowsPath(
        document_path
    ).is_absolute()
    if not is_absolute:
        return str((data_root / stored).resolve())
    if stored.exists():
        return document_path
    candidate = data_root / "uploads" / project_file.parent.name / stored.name
    if candidate.exists():
        return str(candidate.resolve())
    return document_path


def load_index(path: Path) -> DocumentIndex:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    for item in raw["documents"]:
        item["source_path"] = _heal_document_path(item["source_path"], path)
    documents = tuple(_load_document(item) for item in raw["documents"])
    relations = tuple(DocumentRelation(**item) for item in raw.get("relations", []))
    sessions = tuple(_load_session(item) for item in raw.get("import_sessions", []))
    pages = tuple(_load_page(item) for item in raw.get("pages", []))
    regions = tuple(_load_region(item) for item in raw.get("regions", []))
    return DocumentIndex(
        project_id=raw["project_id"],
        project_name=raw["project_name"],
        documents=documents,
        relations=relations,
        import_sessions=sessions,
        pages=pages,
        regions=regions,
        created_at=datetime.fromisoformat(raw["created_at"]),
        updated_at=datetime.fromisoformat(raw["updated_at"]),
    )
