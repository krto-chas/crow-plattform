from crow_accepted_claims import (
    AcceptanceBasis,
    AcceptedClaim,
    AcceptedClaimProvenance,
    AcceptedClaimSet,
)
from crow_decision_engine import (
    ClaimSelector,
    ConditionOperator,
    DecisionOutputTemplate,
    DecisionSeverity,
    MultiClaimRule,
    RuleEvaluationStatus,
    RuleSet,
    evaluate_claims,
    evaluate_expression,
)


def claim(
    claim_id: str,
    subject: str,
    value: str,
    unit: str,
    confidence: float = 0.9,
) -> AcceptedClaim:
    return AcceptedClaim(
        id=claim_id,
        semantic_key=f"key_value|{subject}|has_value|{unit}",
        subject=subject,
        predicate="has_value",
        value=value,
        unit=unit,
        confidence=confidence,
        acceptance_basis=AcceptanceBasis.AUTHORITY_HIERARCHY,
        provenance=AcceptedClaimProvenance(
            cluster_id=f"cluster:{claim_id}",
            authority_decision_id=f"authority:{claim_id}",
            candidate_ids=(f"candidate:{claim_id}",),
            document_ids=(f"document:{claim_id}",),
            framework_id="se.ab04.default",
            applied_rule="document_hierarchy",
            trace=("accepted",),
        ),
        fingerprint=f"fingerprint:{claim_id}",
    )


def velocity_rule() -> MultiClaimRule:
    return MultiClaimRule(
        id="ventilation.velocity.limit",
        name="Velocity limit",
        description="",
        priority=120,
        enabled=True,
        selectors=(
            ClaimSelector(
                alias="airflow",
                subject_regex="airflow",
                unit="L/S",
            ),
            ClaimSelector(
                alias="area",
                subject_regex="duct area",
                unit="M2",
            ),
        ),
        expression="(airflow / 1000) / area",
        comparison=ConditionOperator.GREATER_THAN,
        expected=5.0,
        output=DecisionOutputTemplate(
            category="ventilation",
            severity=DecisionSeverity.HIGH,
            title="Velocity too high",
            conclusion="Calculated velocity exceeds limit.",
            recommended_action="Increase duct area.",
        ),
        source="project rule",
    )


def test_safe_expression_evaluation() -> None:
    assert (
        evaluate_expression(
            "(airflow / 1000) / area",
            {"airflow": 400.0, "area": 0.05},
        )
        == 8.0
    )


def test_multi_claim_rule_emits_combined_decision() -> None:
    claims = AcceptedClaimSet(
        project_id="project",
        claims=(
            claim("airflow", "AHU-03 airflow", "400", "L/S"),
            claim("area", "AHU-03 duct area", "0.05", "M2"),
        ),
    )
    rules = RuleSet(
        id="rules",
        name="Rules",
        version="1",
        rules=(),
        multi_rules=(velocity_rule(),),
    )

    result = evaluate_claims(claims, rules)

    assert result.matched_count == 1
    assert result.multi_evaluations[0].calculated_value == 8.0
    assert result.multi_evaluations[0].status == RuleEvaluationStatus.MATCHED
    assert result.candidates[0].provenance.accepted_claim_ids == (
        "airflow",
        "area",
    )
    assert result.candidates[0].confidence == 0.9


def test_missing_selector_produces_non_match() -> None:
    claims = AcceptedClaimSet(
        project_id="project",
        claims=(claim("airflow", "AHU-03 airflow", "400", "L/S"),),
    )
    rules = RuleSet(
        id="rules",
        name="Rules",
        version="1",
        rules=(),
        multi_rules=(velocity_rule(),),
    )

    result = evaluate_claims(claims, rules)

    assert result.matched_count == 0
    assert result.multi_evaluations[0].status == RuleEvaluationStatus.NOT_MATCHED


def test_invalid_numeric_claim_is_recorded() -> None:
    claims = AcceptedClaimSet(
        project_id="project",
        claims=(
            claim("airflow", "AHU-03 airflow", "unknown", "L/S"),
            claim("area", "AHU-03 duct area", "0.05", "M2"),
        ),
    )
    rules = RuleSet(
        id="rules",
        name="Rules",
        version="1",
        rules=(),
        multi_rules=(velocity_rule(),),
    )

    result = evaluate_claims(claims, rules)

    assert result.matched_count == 0
    assert result.multi_evaluations[0].status == RuleEvaluationStatus.INVALID_INPUT


def test_minimum_confidence_filters_selector() -> None:
    strict_rule = MultiClaimRule(
        id=velocity_rule().id,
        name=velocity_rule().name,
        description="",
        priority=120,
        enabled=True,
        selectors=(
            ClaimSelector(
                alias="airflow",
                subject_regex="airflow",
                unit="L/S",
                minimum_confidence=0.95,
            ),
            velocity_rule().selectors[1],
        ),
        expression=velocity_rule().expression,
        comparison=velocity_rule().comparison,
        expected=velocity_rule().expected,
        output=velocity_rule().output,
        source="project rule",
    )
    claims = AcceptedClaimSet(
        project_id="project",
        claims=(
            claim("airflow", "AHU-03 airflow", "400", "L/S", confidence=0.9),
            claim("area", "AHU-03 duct area", "0.05", "M2"),
        ),
    )

    result = evaluate_claims(
        claims,
        RuleSet(
            id="rules",
            name="Rules",
            version="1",
            rules=(),
            multi_rules=(strict_rule,),
        ),
    )

    assert result.matched_count == 0
