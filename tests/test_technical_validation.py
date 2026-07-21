from crow_accepted_claims import (
    AcceptanceBasis,
    AcceptedClaim,
    AcceptedClaimProvenance,
    AcceptedClaimSet,
)
from crow_technical_validation import (
    RequiredClaim,
    ValidationIssueType,
    ValidationProfile,
    ValidationRequirement,
    ValidationSeverity,
    validate_claims,
)


def claim(
    claim_id: str,
    subject: str,
    value: str,
    unit: str | None,
    confidence: float = 0.9,
) -> AcceptedClaim:
    return AcceptedClaim(
        id=claim_id,
        semantic_key=f"key_value|{subject}|has_value|{unit or ''}",
        subject=subject,
        predicate="has_value",
        value=value,
        unit=unit,
        confidence=confidence,
        acceptance_basis=AcceptanceBasis.CONSENSUS,
        provenance=AcceptedClaimProvenance(
            cluster_id=f"cluster:{claim_id}",
            authority_decision_id=f"authority:{claim_id}",
            candidate_ids=(f"candidate:{claim_id}",),
            document_ids=(f"document:{claim_id}",),
            framework_id="se.ab04.default",
            applied_rule="consistent_sources",
            trace=("accepted",),
        ),
        fingerprint=f"fingerprint:{claim_id}",
    )


def requirement() -> ValidationRequirement:
    return ValidationRequirement(
        id="duct-sizing",
        name="Duct sizing inputs",
        description="",
        severity=ValidationSeverity.BLOCKING,
        required_claims=(
            RequiredClaim(
                alias="airflow",
                subject_regex="airflow",
                unit="L/S",
                minimum_confidence=0.7,
                numeric=True,
            ),
            RequiredClaim(
                alias="area",
                subject_regex="duct area",
                unit="M2",
                minimum_confidence=0.7,
                numeric=True,
            ),
        ),
        source="project rule",
    )


def profile() -> ValidationProfile:
    return ValidationProfile(
        id="validation",
        name="Validation",
        version="1",
        requirements=(requirement(),),
    )


def test_missing_claim_creates_blocking_issue() -> None:
    claims = AcceptedClaimSet(
        project_id="project",
        claims=(claim("airflow", "AHU airflow", "400", "L/S"),),
    )

    result = validate_claims(claims, profile())

    assert result.blocking_count == 1
    assert result.issues[0].issue_type == ValidationIssueType.MISSING_INFORMATION
    assert result.issues[0].missing_aliases == ("area",)


def test_complete_information_has_no_issue() -> None:
    claims = AcceptedClaimSet(
        project_id="project",
        claims=(
            claim("airflow", "AHU airflow", "400", "L/S"),
            claim("area", "AHU duct area", "0.05", "M2"),
        ),
    )

    assert validate_claims(claims, profile()).issues == ()


def test_invalid_numeric_value_is_reported() -> None:
    claims = AcceptedClaimSet(
        project_id="project",
        claims=(
            claim("airflow", "AHU airflow", "unknown", "L/S"),
            claim("area", "AHU duct area", "0.05", "M2"),
        ),
    )

    result = validate_claims(claims, profile())

    assert result.issues[0].issue_type == ValidationIssueType.INVALID_VALUE


def test_low_confidence_is_reported_separately() -> None:
    claims = AcceptedClaimSet(
        project_id="project",
        claims=(
            claim("airflow", "AHU airflow", "400", "L/S", confidence=0.5),
            claim("area", "AHU duct area", "0.05", "M2"),
        ),
    )

    result = validate_claims(claims, profile())

    assert result.issues[0].issue_type == ValidationIssueType.LOW_CONFIDENCE


def test_multiple_matches_are_ambiguous() -> None:
    claims = AcceptedClaimSet(
        project_id="project",
        claims=(
            claim("airflow-a", "AHU airflow", "400", "L/S"),
            claim("airflow-b", "AHU airflow", "410", "L/S"),
            claim("area", "AHU duct area", "0.05", "M2"),
        ),
    )

    result = validate_claims(claims, profile())

    assert result.issues[0].issue_type == ValidationIssueType.AMBIGUOUS_MATCH
