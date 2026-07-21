from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from .document_model import DocumentPage, DocumentRegion


class DocumentStatus(StrEnum):
    NEW = "new"
    INDEXED = "indexed"
    ANALYZED = "analyzed"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class DocumentType(StrEnum):
    DRAWING = "drawing"
    AF = "af"
    AMA = "ama"
    TECHNICAL_SPECIFICATION = "technical_specification"
    ROOM_DESCRIPTION = "room_description"
    FIRE_SAFETY = "fire_safety"
    FUNCTIONAL_DESCRIPTION = "functional_description"
    AS_BUILT = "as_built"
    OPERATING_INSTRUCTION = "operating_instruction"
    ESTIMATE = "estimate"
    QUOTATION = "quotation"
    EMAIL = "email"
    PROTOCOL = "protocol"
    UNKNOWN = "unknown"


class DocumentRole(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    REFERENCE = "reference"
    AUTHORITY = "authority"
    UNKNOWN = "unknown"


class ImportOutcome(StrEnum):
    IMPORTED = "imported"
    DUPLICATE = "duplicate"
    REVISION = "revision"
    OLDER_REVISION = "older_revision"
    FAILED = "failed"


class ImportSessionStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DocumentFingerprint:
    sha256: str
    size_bytes: int
    filename_key: str
    document_number: str | None
    revision: str | None
    page_count: int
    metadata_signature: str


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    creator: str | None = None
    producer: str | None = None
    document_number: str | None = None
    revision: str | None = None
    discipline: str | None = None
    language: str = "und"


@dataclass(frozen=True, slots=True)
class CrowDocument:
    id: str
    filename: str
    source_path: str
    fingerprint: DocumentFingerprint
    metadata: DocumentMetadata
    document_type: DocumentType
    role: DocumentRole
    status: DocumentStatus
    imported_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    supersedes_document_id: str | None = None
    import_session_id: str | None = None

    @property
    def path(self) -> Path:
        return Path(self.source_path)


@dataclass(frozen=True, slots=True)
class DocumentRelation:
    source_document_id: str
    target_document_id: str
    relation_type: str
    confidence: float
    evidence: str


@dataclass(frozen=True, slots=True)
class ImportItemResult:
    path: str
    outcome: ImportOutcome
    document_id: str | None = None
    related_document_id: str | None = None
    message: str = ""
    error_type: str | None = None


@dataclass(frozen=True, slots=True)
class ImportSession:
    id: str
    started_at: datetime
    completed_at: datetime | None
    status: ImportSessionStatus
    requested_paths: tuple[str, ...]
    results: tuple[ImportItemResult, ...] = ()

    @property
    def imported_count(self) -> int:
        return sum(
            result.outcome in {ImportOutcome.IMPORTED, ImportOutcome.REVISION}
            for result in self.results
        )

    @property
    def failed_count(self) -> int:
        return sum(result.outcome == ImportOutcome.FAILED for result in self.results)


@dataclass(frozen=True, slots=True)
class DocumentIndex:
    project_id: str
    project_name: str
    documents: tuple[CrowDocument, ...] = ()
    relations: tuple[DocumentRelation, ...] = ()
    import_sessions: tuple[ImportSession, ...] = ()
    pages: tuple[DocumentPage, ...] = ()
    regions: tuple[DocumentRegion, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def active_documents(self) -> tuple[CrowDocument, ...]:
        return tuple(
            document
            for document in self.documents
            if document.status not in {DocumentStatus.SUPERSEDED, DocumentStatus.ARCHIVED}
        )
