from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ObservationType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    UNIT = "unit"
    REFERENCE = "reference"
    DATE = "date"
    HEADING = "heading"


class ObservationSource(StrEnum):
    EMBEDDED_PDF_TEXT = "embedded_pdf_text"


@dataclass(frozen=True, slots=True)
class SourceLocator:
    document_id: str
    page_id: str
    page_number: int
    region_id: str
    character_start: int
    character_end: int

    @property
    def value(self) -> str:
        return (
            f"{self.document_id}#page={self.page_number}"
            f"&region={self.region_id}"
            f"&chars={self.character_start}-{self.character_end}"
        )


@dataclass(frozen=True, slots=True)
class ObservationEvidence:
    source: ObservationSource
    source_text: str
    confidence: float
    locator: SourceLocator
    page_sha256: str


@dataclass(frozen=True, slots=True)
class Observation:
    id: str
    observation_type: ObservationType
    value: str
    normalized_value: str
    content_sha256: str
    evidence: ObservationEvidence


@dataclass(frozen=True, slots=True)
class ObservationCollection:
    project_id: str
    observations: tuple[Observation, ...] = ()

    @property
    def duplicate_count(self) -> int:
        unique = {item.content_sha256 for item in self.observations}
        return len(self.observations) - len(unique)

    @property
    def unique_content_count(self) -> int:
        return len({item.content_sha256 for item in self.observations})
