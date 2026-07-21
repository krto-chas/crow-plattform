from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from crow_authority import AuthorityFramework, DocumentAuthorityMetadata


class ContractFramework(StrEnum):
    AB04 = "ab04"
    ABT06 = "abt06"
    UNKNOWN = "unknown"


class DiscoveryFindingType(StrEnum):
    CONTRACT_FRAMEWORK = "contract_framework"
    DOCUMENT_CLASSIFICATION = "document_classification"
    AUTHORITY_OVERRIDE = "authority_override"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class DiscoveryEvidence:
    document_id: str
    page_number: int | None
    excerpt: str
    locator: str


@dataclass(frozen=True, slots=True)
class DiscoveryFinding:
    finding_type: DiscoveryFindingType
    value: str
    confidence: float
    explanation: str
    evidence: tuple[DiscoveryEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class AuthorityDiscoveryResult:
    project_id: str
    contract_framework: ContractFramework
    framework: AuthorityFramework
    documents: tuple[DocumentAuthorityMetadata, ...]
    findings: tuple[DiscoveryFinding, ...]
    requires_review: bool
