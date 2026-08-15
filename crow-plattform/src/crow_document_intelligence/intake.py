from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pypdf import PdfReader

from .classification import classify_document
from .extraction import extract_pdf_structure
from .metadata import normalize_filename_key, parse_filename_metadata
from .models import (
    CrowDocument,
    DocumentFingerprint,
    DocumentIndex,
    DocumentMetadata,
    DocumentStatus,
    ImportItemResult,
    ImportOutcome,
    ImportSession,
    ImportSessionStatus,
)
from .relations import infer_document_relations
from .revision import is_newer_or_equal, logical_identity, normalize_revision


class UnsupportedDocumentError(ValueError):
    pass


def fingerprint_document(path: Path) -> tuple[DocumentFingerprint, DocumentMetadata]:
    if path.suffix.lower() != ".pdf":
        raise UnsupportedDocumentError(f"Only PDF is supported in B1: {path.name}")

    payload = path.read_bytes()
    reader = PdfReader(path)
    raw: Any = reader.metadata or {}
    filename_metadata = parse_filename_metadata(path.name)
    metadata = replace(
        filename_metadata,
        title=str(raw.get("/Title") or "").strip() or filename_metadata.title,
        author=str(raw.get("/Author") or "").strip() or None,
        subject=str(raw.get("/Subject") or "").strip() or None,
        creator=str(raw.get("/Creator") or "").strip() or None,
        producer=str(raw.get("/Producer") or "").strip() or None,
    )
    material = "|".join(
        [
            metadata.title or "",
            metadata.author or "",
            metadata.subject or "",
            str(len(reader.pages)),
            metadata.document_number or "",
            metadata.revision or "",
        ]
    ).encode()
    return (
        DocumentFingerprint(
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            filename_key=normalize_filename_key(path.name),
            document_number=metadata.document_number,
            revision=metadata.revision,
            page_count=len(reader.pages),
            metadata_signature=hashlib.sha256(material).hexdigest(),
        ),
        metadata,
    )


def ingest_document(path: Path, session_id: str | None = None) -> CrowDocument:
    resolved = path.resolve()
    fingerprint, metadata = fingerprint_document(resolved)
    document_type, role = classify_document(resolved.name, metadata.title)
    return CrowDocument(
        id=f"doc:{uuid4()}",
        filename=resolved.name,
        source_path=str(resolved),
        fingerprint=fingerprint,
        metadata=metadata,
        document_type=document_type,
        role=role,
        status=DocumentStatus.INDEXED,
        import_session_id=session_id,
    )


def import_documents(
    index: DocumentIndex,
    paths: list[Path],
) -> tuple[DocumentIndex, ImportSession]:
    started_at = datetime.now(UTC)
    session_id = f"import:{uuid4()}"
    documents = list(index.documents)
    pages = list(index.pages)
    regions = list(index.regions)
    results: list[ImportItemResult] = []
    checksums = {document.fingerprint.sha256: document for document in documents}

    for path in sorted(paths, key=lambda item: item.name.lower()):
        try:
            candidate = ingest_document(path, session_id=session_id)
            duplicate = checksums.get(candidate.fingerprint.sha256)
            if duplicate is not None:
                results.append(
                    ImportItemResult(
                        path=str(path),
                        outcome=ImportOutcome.DUPLICATE,
                        related_document_id=duplicate.id,
                        message=(
                            f"Duplicate skipped: {candidate.filename} matches {duplicate.filename}"
                        ),
                    )
                )
                continue

            previous = [
                document
                for document in documents
                if logical_identity(document) == logical_identity(candidate)
                and document.status not in {DocumentStatus.ARCHIVED, DocumentStatus.SUPERSEDED}
            ]
            outcome = ImportOutcome.IMPORTED
            related_document_id: str | None = None

            if previous:
                current = max(
                    previous,
                    key=lambda document: (
                        normalize_revision(document.metadata.revision),
                        document.imported_at,
                    ),
                )
                related_document_id = current.id
                if is_newer_or_equal(candidate, current):
                    documents = [
                        replace(document, status=DocumentStatus.SUPERSEDED)
                        if document.id == current.id
                        else document
                        for document in documents
                    ]
                    candidate = replace(
                        candidate,
                        supersedes_document_id=current.id,
                    )
                    outcome = ImportOutcome.REVISION
                else:
                    candidate = replace(
                        candidate,
                        status=DocumentStatus.SUPERSEDED,
                    )
                    outcome = ImportOutcome.OLDER_REVISION

            documents.append(candidate)
            if candidate.status != DocumentStatus.SUPERSEDED:
                extracted_pages, extracted_regions = extract_pdf_structure(
                    candidate.path,
                    candidate.id,
                )
                pages.extend(extracted_pages)
                regions.extend(extracted_regions)
            checksums[candidate.fingerprint.sha256] = candidate
            results.append(
                ImportItemResult(
                    path=str(path),
                    outcome=outcome,
                    document_id=candidate.id,
                    related_document_id=related_document_id,
                    message=(
                        f"{candidate.filename}: "
                        f"{candidate.document_type.value}/{candidate.role.value}, "
                        f"{candidate.fingerprint.page_count} pages"
                    ),
                )
            )
        except Exception as exc:
            results.append(
                ImportItemResult(
                    path=str(path),
                    outcome=ImportOutcome.FAILED,
                    message=str(exc),
                    error_type=type(exc).__name__,
                )
            )

    completed_at = datetime.now(UTC)
    failed_count = sum(result.outcome == ImportOutcome.FAILED for result in results)
    status = (
        ImportSessionStatus.COMPLETED_WITH_ERRORS if failed_count else ImportSessionStatus.COMPLETED
    )
    session = ImportSession(
        id=session_id,
        started_at=started_at,
        completed_at=completed_at,
        status=status,
        requested_paths=tuple(str(path) for path in paths),
        results=tuple(results),
    )
    updated_documents = tuple(documents)
    updated = replace(
        index,
        documents=updated_documents,
        relations=infer_document_relations(updated_documents),
        import_sessions=(*index.import_sessions, session),
        pages=tuple(pages),
        regions=tuple(regions),
        updated_at=completed_at,
    )
    return updated, session


def collect_pdf_paths(inputs: list[Path], recursive: bool = False) -> list[Path]:
    output: list[Path] = []
    for item in inputs:
        if item.is_file():
            output.append(item)
        elif item.is_dir():
            pattern = "**/*" if recursive else "*"
            output.extend(path for path in item.glob(pattern) if path.is_file())
        else:
            output.extend(path for path in item.parent.glob(item.name) if path.is_file())
    return sorted(set(path.resolve() for path in output), key=lambda path: path.name.lower())
