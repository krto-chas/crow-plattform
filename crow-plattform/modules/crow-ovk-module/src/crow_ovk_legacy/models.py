from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LegacySourceKind(StrEnum):
    PDF = "pdf"
    XLSX = "xlsx"


class LegacyFactStatus(StrEnum):
    EXTRACTED = "extracted"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class LegacySourceRef:
    source_id: str
    filename: str
    kind: LegacySourceKind
    locator: str
    sha256: str


@dataclass(frozen=True, slots=True)
class LegacyFact:
    field: str
    value: str
    confidence: str
    status: LegacyFactStatus
    source: LegacySourceRef


@dataclass(frozen=True, slots=True)
class LegacyReviewItem:
    reason: str
    source_text: str
    source: LegacySourceRef


@dataclass(frozen=True, slots=True)
class LegacyImportPreview:
    project_id: str
    filename: str
    kind: LegacySourceKind
    source_sha256: str
    facts: tuple[LegacyFact, ...] = ()
    review: tuple[LegacyReviewItem, ...] = ()

    @property
    def ready_for_commit(self) -> bool:
        return bool(self.facts) and not self.review
