from crow_accepted_claims import (
    AcceptanceBasis,
    AcceptedClaim,
    AcceptedClaimProvenance,
    AcceptedClaimSet,
)
from crow_decision_engine import (
    ConditionOperator,
    DecisionOutputTemplate,
    DecisionSeverity,
    RuleCondition,
    RuleEvaluationStatus,
    RuleSet,
    TechnicalDecisionRule,
    evaluate_claims,
)


def claim(value: str = "400", unit: str | None = "L/S") -> AcceptedClaim:
    return AcceptedClaim(
        id="accepted:1",
        semantic_key="key_value|ahu-03 airflow|has_value|l/s",
        subject="AHU-03 airflow",
        predicate="has_value",
        value=value,
        unit=unit,
        confidence=0.93,
        acceptance_basis=AcceptanceBasis.AUTHORITY_HIERARCHY,
        provenance=AcceptedClaimProvenance(
            cluster_id="cluster:1",
            authority_decision_id="decision:1",
            candidate_ids=("candidate:1",),
            document_ids=("description:1",),
            framework_id="se.ab04.default",
            applied_rule="document_hierarchy",
            trace=("description outranks drawing",),
        ),
        fingerprint="claim-fingerprint",
    )


def rule() -> TechnicalDecisionRule:
    return TechnicalDecisionRule(
        id="ventilation.airflow.high",
        name="High airflow",
        description="",
        priority=100,
        enabled=True,
        conditions=(
            RuleCondition("predicate", ConditionOperator.EQUALS, "has_value"),
            RuleCondition("unit", ConditionOperator.EQUALS, "L/S"),
            RuleCondition("value", ConditionOperator.GREATER_THAN, 350),
        ),
        output=DecisionOutputTemplate(
            category="ventilation",
            severity=DecisionSeverity.MEDIUM,
            title="High accepted airflow",
            conclusion="Accepted airflow exceeds threshold.",
            recommended_action="Verify sizing.",
        ),
        source="project rule",
    )


def test_matching_rule_creates_traceable_candidate() -> None:
    result = evaluate_claims(
        AcceptedClaimSet(project_id="project", claims=(claim(),)),
        RuleSet(id="rules", name="Rules", version="1", rules=(rule(),)),
    )

    assert result.matched_count == 1
    candidate = result.candidates[0]
    assert candidate.confidence == 0.93
    assert candidate.provenance.accepted_claim_ids == ("accepted:1",)
    assert candidate.provenance.document_ids == ("description:1",)
    assert candidate.status == "proposed"


def test_non_matching_rule_does_not_create_candidate() -> None:
    result = evaluate_claims(
        AcceptedClaimSet(project_id="project", claims=(claim("300"),)),
        RuleSet(id="rules", name="Rules", version="1", rules=(rule(),)),
    )

    assert result.matched_count == 0
    assert result.evaluations[0].status == RuleEvaluationStatus.NOT_MATCHED


def test_disabled_rule_is_not_evaluated() -> None:
    disabled = TechnicalDecisionRule(
        id=rule().id,
        name=rule().name,
        description="",
        priority=100,
        enabled=False,
        conditions=rule().conditions,
        output=rule().output,
        source="project rule",
    )
    result = evaluate_claims(
        AcceptedClaimSet(project_id="project", claims=(claim(),)),
        RuleSet(id="rules", name="Rules", version="1", rules=(disabled,)),
    )

    assert result.evaluated_count == 0


def test_output_is_deterministic() -> None:
    claims = AcceptedClaimSet(project_id="project", claims=(claim(),))
    rules = RuleSet(id="rules", name="Rules", version="1", rules=(rule(),))

    first = evaluate_claims(claims, rules)
    second = evaluate_claims(claims, rules)

    assert first == second
    assert first.candidates[0].id == second.candidates[0].id


def test_invalid_numeric_input_is_recorded_not_emitted() -> None:
    result = evaluate_claims(
        AcceptedClaimSet(project_id="project", claims=(claim("unknown"),)),
        RuleSet(id="rules", name="Rules", version="1", rules=(rule(),)),
    )

    assert result.matched_count == 0
    assert result.evaluations[0].status == RuleEvaluationStatus.INVALID_INPUT
