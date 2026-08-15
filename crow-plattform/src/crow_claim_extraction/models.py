from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ClaimCandidateType(StrEnum):
    KEY_VALUE = "key_value"
    QUANTITY = "quantity"
    REFERENCE = "reference"


class ClaimCandidateStatus(StrEnum):
    PROPOSED = "proposed"
    REJECTED = "rejected"
    PROMOTED = "promoted"


@dataclass(frozen=True, slots=True)
class ClaimProvenance:
    observation_ids: tuple[str, ...]
    document_id: str
    page_number: int
    region_id: str
    locator_values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClaimCandidate:
    id: str
    candidate_type: ClaimCandidateType
    subject: str
    predicate: str
    value: str
    normalized_value: str
    unit: str | None
    confidence: float
    status: ClaimCandidateStatus
    provenance: ClaimProvenance
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ClaimCandidateCollection:
    project_id: str
    candidates: tuple[ClaimCandidate, ...] = ()

    @property
    def unique_count(self) -> int:
        return len({candidate.fingerprint for candidate in self.candidates})

    @property
    def duplicate_count(self) -> int:
        return len(self.candidates) - self.unique_count
