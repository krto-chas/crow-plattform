from __future__ import annotations

import re
from datetime import date

from crow_authority import (
    AuthorityFramework,
    DocumentAuthorityMetadata,
    DocumentAuthorityType,
    ab04_framework,
    project_framework,
)
from crow_document_intelligence import DocumentIndex, DocumentType

from .models import (
    AuthorityDiscoveryResult,
    ContractFramework,
    DiscoveryEvidence,
    DiscoveryFinding,
    DiscoveryFindingType,
)

_AB04 = re.compile(r"\bAB\s*04\b", re.IGNORECASE)
_ABT06 = re.compile(r"\bABT\s*06\b", re.IGNORECASE)
_AF_SECTION = re.compile(r"\bAF[CD]\.111\b", re.IGNORECASE)
_DRAWING_BEFORE_DESCRIPTION = re.compile(
    r"ritning(?:ar|en)?\s+(?:äger|har|skall ha|gäller)\s+(?:företräde|före)"
    r".*?beskrivning|ritningar\s+före\s+beskrivningar",
    re.IGNORECASE | re.DOTALL,
)
_DESCRIPTION_BEFORE_DRAWING = re.compile(
    r"beskrivning(?:ar|en)?\s+(?:äger|har|skall ha|gäller)\s+(?:företräde|före)"
    r".*?ritning|beskrivningar\s+före\s+ritningar",
    re.IGNORECASE | re.DOTALL,
)


def _all_text(index: DocumentIndex) -> str:
    return "\n".join(page.text for page in index.pages)


def _evidence(index: DocumentIndex, pattern: re.Pattern[str]) -> tuple[DiscoveryEvidence, ...]:
    items: list[DiscoveryEvidence] = []
    for page in index.pages:
        match = pattern.search(page.text)
        if match:
            start = max(0, match.start() - 100)
            end = min(len(page.text), match.end() + 180)
            items.append(
                DiscoveryEvidence(
                    document_id=page.document_id,
                    page_number=page.page_number,
                    excerpt=" ".join(page.text[start:end].split()),
                    locator=page.locator,
                )
            )
    return tuple(items)


def _contract_framework(index: DocumentIndex) -> tuple[ContractFramework, DiscoveryFinding]:
    ab04 = _evidence(index, _AB04)
    abt06 = _evidence(index, _ABT06)
    if abt06 and not ab04:
        return ContractFramework.ABT06, DiscoveryFinding(
            DiscoveryFindingType.CONTRACT_FRAMEWORK,
            "abt06",
            0.95,
            "ABT 06 detected in project text.",
            abt06[:3],
        )
    if ab04 and not abt06:
        return ContractFramework.AB04, DiscoveryFinding(
            DiscoveryFindingType.CONTRACT_FRAMEWORK,
            "ab04",
            0.95,
            "AB 04 detected in project text.",
            ab04[:3],
        )
    if ab04 and abt06:
        return ContractFramework.UNKNOWN, DiscoveryFinding(
            DiscoveryFindingType.REVIEW_REQUIRED,
            "mixed_contract_frameworks",
            0.5,
            "Both AB 04 and ABT 06 were found; human confirmation is required.",
            (ab04 + abt06)[:4],
        )
    return ContractFramework.UNKNOWN, DiscoveryFinding(
        DiscoveryFindingType.REVIEW_REQUIRED,
        "contract_framework_not_found",
        0.2,
        "Neither AB 04 nor ABT 06 was detected.",
        (),
    )


def _authority_type(
    document_type: DocumentType, filename: str, title: str
) -> tuple[DocumentAuthorityType, float, str]:
    key = f"{filename} {title}".casefold()
    if document_type == DocumentType.DRAWING:
        return (
            DocumentAuthorityType.DRAWING,
            0.98,
            "Document index classifies the file as a drawing.",
        )
    if document_type == DocumentType.AF:
        return (
            DocumentAuthorityType.ADMINISTRATIVE_SPECIFICATIONS,
            0.98,
            "Document index classifies the file as AF.",
        )
    if document_type == DocumentType.TECHNICAL_SPECIFICATION:
        return (
            DocumentAuthorityType.TECHNICAL_DESCRIPTION,
            0.96,
            "Document index classifies the file as a technical specification.",
        )
    if document_type == DocumentType.QUOTATION:
        return DocumentAuthorityType.TENDER, 0.85, "Quotation mapped to tender/anbud."
    mappings = (
        ("kontrakt", DocumentAuthorityType.CONTRACT),
        ("beställning", DocumentAuthorityType.ORDER),
        ("anbud", DocumentAuthorityType.TENDER),
        ("à-pris", DocumentAuthorityType.PRICED_BILL),
        ("apris", DocumentAuthorityType.PRICED_BILL),
        ("mängdförteckning", DocumentAuthorityType.UNPRICED_BILL),
        ("teknisk beskrivning", DocumentAuthorityType.TECHNICAL_DESCRIPTION),
        ("ritning", DocumentAuthorityType.DRAWING),
    )
    for token, authority_type in mappings:
        if token in key:
            return authority_type, 0.78, f"Filename/title contains '{token}'."
    return DocumentAuthorityType.UNKNOWN, 0.2, "No reliable authority classification was found."


def _discover_documents(
    index: DocumentIndex,
) -> tuple[tuple[DocumentAuthorityMetadata, ...], tuple[DiscoveryFinding, ...], bool]:
    metadata: list[DocumentAuthorityMetadata] = []
    findings: list[DiscoveryFinding] = []
    requires_review = False
    for document in index.active_documents:
        authority_type, confidence, reason = _authority_type(
            document.document_type, document.filename, document.metadata.title or ""
        )
        if authority_type == DocumentAuthorityType.UNKNOWN:
            requires_review = True
        issue_date: date | None = document.imported_at.date()
        metadata.append(
            DocumentAuthorityMetadata(
                document_id=document.id,
                authority_type=authority_type,
                title=document.metadata.title or document.filename,
                issue_date=issue_date,
                revision=document.metadata.revision,
            )
        )
        findings.append(
            DiscoveryFinding(
                DiscoveryFindingType.DOCUMENT_CLASSIFICATION,
                f"{document.id}:{authority_type.value}",
                confidence,
                reason,
                (DiscoveryEvidence(document.id, None, document.filename, document.source_path),),
            )
        )
    return tuple(metadata), tuple(findings), requires_review


def _discover_override(
    index: DocumentIndex,
) -> tuple[AuthorityFramework, DiscoveryFinding | None, bool]:
    base = ab04_framework()
    section_evidence = _evidence(index, _AF_SECTION)
    drawing_first = _evidence(index, _DRAWING_BEFORE_DESCRIPTION)
    description_first = _evidence(index, _DESCRIPTION_BEFORE_DRAWING)
    if drawing_first:
        hierarchy = tuple(
            item
            for item in base.hierarchy
            if item
            not in {DocumentAuthorityType.DRAWING, DocumentAuthorityType.TECHNICAL_DESCRIPTION}
        )
        insert_at = min(
            base.hierarchy.index(DocumentAuthorityType.DRAWING),
            base.hierarchy.index(DocumentAuthorityType.TECHNICAL_DESCRIPTION),
        )
        updated: list[DocumentAuthorityType] = list(hierarchy)
        updated[insert_at:insert_at] = [
            DocumentAuthorityType.DRAWING,
            DocumentAuthorityType.TECHNICAL_DESCRIPTION,
        ]
        framework = project_framework(
            tuple(updated),
            source="Automatically discovered in AFC/AFD.111",
            framework_id="project.discovered.afc-afd-111",
        )
        return (
            framework,
            DiscoveryFinding(
                DiscoveryFindingType.AUTHORITY_OVERRIDE,
                "drawing_before_technical_description",
                0.9,
                "Project text explicitly gives drawings precedence over descriptions.",
                (section_evidence + drawing_first)[:4],
            ),
            False,
        )
    if description_first:
        return (
            base,
            DiscoveryFinding(
                DiscoveryFindingType.AUTHORITY_OVERRIDE,
                "technical_description_before_drawing",
                0.9,
                "Project text confirms the default precedence of descriptions over drawings.",
                (section_evidence + description_first)[:4],
            ),
            False,
        )
    if section_evidence:
        return (
            base,
            DiscoveryFinding(
                DiscoveryFindingType.REVIEW_REQUIRED,
                "afc_afd_111_requires_interpretation",
                0.55,
                "AFC/AFD.111 was found, but no supported explicit precedence phrase was extracted.",
                section_evidence[:3],
            ),
            True,
        )
    return base, None, False


def discover_authority(index: DocumentIndex) -> AuthorityDiscoveryResult:
    contract, contract_finding = _contract_framework(index)
    documents, document_findings, document_review = _discover_documents(index)
    framework, override_finding, override_review = _discover_override(index)
    findings = [contract_finding, *document_findings]
    if override_finding is not None:
        findings.append(override_finding)
    requires_review = contract == ContractFramework.UNKNOWN or document_review or override_review
    return AuthorityDiscoveryResult(
        project_id=index.project_id,
        contract_framework=contract,
        framework=framework,
        documents=documents,
        findings=tuple(findings),
        requires_review=requires_review,
    )
