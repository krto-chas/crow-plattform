from __future__ import annotations

import hashlib
import re

from crow_accepted_claims import AcceptedClaim, AcceptedClaimSet

from .models import (
    RequiredClaim,
    TechnicalValidationIssue,
    TechnicalValidationResult,
    ValidationIssueType,
    ValidationProfile,
    ValidationRequirement,
)


def _matches(claim: AcceptedClaim, required: RequiredClaim) -> bool:
    if required.subject is not None and claim.subject.casefold() != required.subject.casefold():
        return False
    if required.subject_regex is not None:
        if re.search(required.subject_regex, claim.subject, re.IGNORECASE) is None:
            return False
    if required.predicate is not None:
        if claim.predicate.casefold() != required.predicate.casefold():
            return False
    if required.unit is not None:
        if claim.unit is None or claim.unit.casefold() != required.unit.casefold():
            return False
    if required.semantic_key_contains is not None:
        if required.semantic_key_contains.casefold() not in claim.semantic_key.casefold():
            return False
    return True


def _invalid_reason(claim: AcceptedClaim, required: RequiredClaim) -> str | None:
    if claim.confidence < required.minimum_confidence:
        return "low_confidence"
    if required.numeric:
        try:
            float(claim.value.replace(",", "."))
        except ValueError:
            return "invalid_numeric"
    if required.allowed_values:
        allowed = {value.casefold() for value in required.allowed_values}
        if claim.value.casefold() not in allowed:
            return "invalid_allowed_value"
    return None


def _issue(
    requirement: ValidationRequirement,
    issue_type: ValidationIssueType,
    explanation: str,
    missing_aliases: tuple[str, ...],
    claims: tuple[AcceptedClaim, ...],
) -> TechnicalValidationIssue:
    material = "|".join(
        (
            requirement.id,
            issue_type.value,
            *missing_aliases,
            *(claim.fingerprint for claim in claims),
        )
    )
    fingerprint = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return TechnicalValidationIssue(
        id=f"technical-validation:{fingerprint}",
        requirement_id=requirement.id,
        issue_type=issue_type,
        severity=requirement.severity,
        title=requirement.name,
        explanation=explanation,
        missing_aliases=missing_aliases,
        related_claim_ids=tuple(claim.id for claim in claims),
        document_ids=tuple(
            dict.fromkeys(
                document_id for claim in claims for document_id in claim.provenance.document_ids
            )
        ),
        recommended_action="Complete or verify the required technical information.",
        fingerprint=fingerprint,
    )


def validate_claims(
    claims: AcceptedClaimSet,
    profile: ValidationProfile,
) -> TechnicalValidationResult:
    issues: list[TechnicalValidationIssue] = []
    checked = 0

    for requirement in sorted(
        (item for item in profile.requirements if item.enabled),
        key=lambda item: item.id,
    ):
        checked += 1
        missing: list[str] = []
        invalid_claims: list[AcceptedClaim] = []
        ambiguous_claims: list[AcceptedClaim] = []

        for required in requirement.required_claims:
            matches = tuple(claim for claim in claims.claims if _matches(claim, required))
            if not matches:
                missing.append(required.alias)
                continue
            valid = tuple(claim for claim in matches if _invalid_reason(claim, required) is None)
            if not valid:
                invalid_claims.extend(matches)
            elif len(valid) > 1:
                ambiguous_claims.extend(valid)

        if missing:
            issues.append(
                _issue(
                    requirement,
                    ValidationIssueType.MISSING_INFORMATION,
                    "Required accepted claims are missing.",
                    tuple(missing),
                    (),
                )
            )
        if invalid_claims:
            issue_type = (
                ValidationIssueType.LOW_CONFIDENCE
                if all(
                    any(
                        _matches(claim, required) and claim.confidence < required.minimum_confidence
                        for required in requirement.required_claims
                    )
                    for claim in invalid_claims
                )
                else ValidationIssueType.INVALID_VALUE
            )
            issues.append(
                _issue(
                    requirement,
                    issue_type,
                    "Matching claims exist but do not satisfy validation constraints.",
                    (),
                    tuple(dict.fromkeys(invalid_claims)),
                )
            )
        if ambiguous_claims:
            issues.append(
                _issue(
                    requirement,
                    ValidationIssueType.AMBIGUOUS_MATCH,
                    "Several accepted claims satisfy the same required role.",
                    (),
                    tuple(dict.fromkeys(ambiguous_claims)),
                )
            )

    return TechnicalValidationResult(
        project_id=claims.project_id,
        profile_id=profile.id,
        issues=tuple(sorted(issues, key=lambda item: (item.requirement_id, item.id))),
        checked_requirements=checked,
    )
