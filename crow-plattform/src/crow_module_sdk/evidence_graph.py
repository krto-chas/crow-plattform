from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .models import Claim, Evidence


@dataclass(frozen=True, slots=True)
class EvidenceIntegrityIssue:
    code: str
    message: str
    evidence_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceIntegrityReport:
    passed: bool
    issues: tuple[EvidenceIntegrityIssue, ...]


def validate_evidence_integrity(
    claims: Iterable[Claim],
    evidence: Iterable[Evidence],
) -> EvidenceIntegrityReport:
    claim_ids = {claim.id for claim in claims}
    evidence_items = tuple(evidence)
    issues: list[EvidenceIntegrityIssue] = []

    seen: set[str] = set()
    for item in evidence_items:
        if item.id in seen:
            issues.append(
                EvidenceIntegrityIssue(
                    "EVI-001",
                    "Duplicate evidence id",
                    item.id,
                )
            )
        seen.add(item.id)

        missing_claims = tuple(sorted(set(item.source_claim_ids) - claim_ids))
        if missing_claims:
            issues.append(
                EvidenceIntegrityIssue(
                    "EVI-002",
                    "Evidence references unknown claims: " + ", ".join(missing_claims),
                    item.id,
                )
            )

        if not item.statement.strip():
            issues.append(
                EvidenceIntegrityIssue(
                    "EVI-003",
                    "Evidence statement must not be empty",
                    item.id,
                )
            )

        if item.kind == "rule" and not item.rule_id:
            issues.append(
                EvidenceIntegrityIssue(
                    "EVI-004",
                    "Rule evidence requires rule_id",
                    item.id,
                )
            )

    return EvidenceIntegrityReport(passed=not issues, issues=tuple(issues))
