from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ValidationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class ValidationIssueType(StrEnum):
    MISSING_INFORMATION = "missing_information"
    INVALID_VALUE = "invalid_value"
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS_MATCH = "ambiguous_match"


@dataclass(frozen=True, slots=True)
class RequiredClaim:
    alias: str
    subject: str | None = None
    subject_regex: str | None = None
    predicate: str | None = None
    unit: str | None = None
    semantic_key_contains: str | None = None
    minimum_confidence: float = 0.0
    numeric: bool = False
    allowed_values: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationRequirement:
    id: str
    name: str
    description: str
    severity: ValidationSeverity
    required_claims: tuple[RequiredClaim, ...]
    source: str
    enabled: bool = True
    version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class ValidationProfile:
    id: str
    name: str
    version: str
    requirements: tuple[ValidationRequirement, ...]


@dataclass(frozen=True, slots=True)
class TechnicalValidationIssue:
    id: str
    requirement_id: str
    issue_type: ValidationIssueType
    severity: ValidationSeverity
    title: str
    explanation: str
    missing_aliases: tuple[str, ...]
    related_claim_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    recommended_action: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class TechnicalValidationResult:
    project_id: str
    profile_id: str
    issues: tuple[TechnicalValidationIssue, ...] = ()
    checked_requirements: int = 0

    @property
    def blocking_count(self) -> int:
        return sum(issue.severity == ValidationSeverity.BLOCKING for issue in self.issues)
