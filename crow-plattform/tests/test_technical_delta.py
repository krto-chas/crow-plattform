from crow_decision_engine import (
    DecisionEvaluationResult,
    DecisionSeverity,
    TechnicalDecisionCandidate,
    TechnicalDecisionProvenance,
)
from crow_technical_delta import (
    BaselineItem,
    ChangeDirection,
    DeltaType,
    TechnicalBaseline,
    ValueKind,
    compare_approved_decisions,
)
from crow_technical_review import (
    ReviewRecord,
    ReviewStatus,
    ReviewTargetType,
    TechnicalReviewSet,
)


def candidate(
    decision_id: str = "decision:1",
    conclusion: str = "New technical requirement.",
) -> TechnicalDecisionCandidate:
    return TechnicalDecisionCandidate(
        id=decision_id,
        category="ventilation",
        severity=DecisionSeverity.HIGH,
        title="Airflow requirement",
        conclusion=conclusion,
        recommended_action="Update design.",
        confidence=0.91,
        priority=100,
        status="proposed",
        provenance=TechnicalDecisionProvenance(
            accepted_claim_ids=("accepted:1",),
            authority_decision_ids=("authority:1",),
            cluster_ids=("cluster:1",),
            document_ids=("document:1",),
            rule_id="rule:1",
            rule_set_id="rules",
            rule_version="1.0.0",
            trace=("matched",),
        ),
        fingerprint=f"fingerprint:{decision_id}",
    )


def reviews(status: ReviewStatus = ReviewStatus.APPROVED) -> TechnicalReviewSet:
    return TechnicalReviewSet(
        project_id="project",
        records=(
            ReviewRecord(
                target_id="decision:1",
                target_type=ReviewTargetType.TECHNICAL_DECISION,
                status=status,
                latest_event_id="event:1",
            ),
        ),
    )


def test_approved_decision_without_baseline_is_added() -> None:
    result = compare_approved_decisions(
        TechnicalBaseline(project_id="project", baseline_id="base", name="Base"),
        DecisionEvaluationResult(
            project_id="project",
            rule_set_id="rules",
            candidates=(candidate(),),
        ),
        reviews(),
    )

    assert result.deltas[0].delta_type == DeltaType.ADDED
    assert result.deltas[0].provenance.review_event_id == "event:1"


def test_changed_baseline_item_is_modified() -> None:
    baseline = TechnicalBaseline(
        project_id="project",
        baseline_id="base",
        name="Base",
        items=(
            BaselineItem(
                id="base:1",
                comparison_key="ventilation|airflow requirement",
                category="ventilation",
                title="Airflow requirement",
                value="Original technical requirement.",
            ),
        ),
    )

    result = compare_approved_decisions(
        baseline,
        DecisionEvaluationResult(
            project_id="project",
            rule_set_id="rules",
            candidates=(candidate(),),
        ),
        reviews(),
    )

    assert result.deltas[0].delta_type == DeltaType.MODIFIED
    assert result.deltas[0].baseline_value == "Original technical requirement."


def test_equal_value_is_unchanged() -> None:
    value = "New technical requirement."
    baseline = TechnicalBaseline(
        project_id="project",
        baseline_id="base",
        name="Base",
        items=(
            BaselineItem(
                id="base:1",
                comparison_key="ventilation|airflow requirement",
                category="ventilation",
                title="Airflow requirement",
                value=value,
            ),
        ),
    )

    result = compare_approved_decisions(
        baseline,
        DecisionEvaluationResult(
            project_id="project",
            rule_set_id="rules",
            candidates=(candidate(conclusion=value),),
        ),
        reviews(),
    )

    assert result.deltas[0].delta_type == DeltaType.UNCHANGED
    assert result.changed_count == 0


def test_baseline_without_approved_decision_is_removed() -> None:
    baseline = TechnicalBaseline(
        project_id="project",
        baseline_id="base",
        name="Base",
        items=(
            BaselineItem(
                id="base:1",
                comparison_key="ventilation|airflow requirement",
                category="ventilation",
                title="Airflow requirement",
                value="Original.",
            ),
        ),
    )

    result = compare_approved_decisions(
        baseline,
        DecisionEvaluationResult(
            project_id="project",
            rule_set_id="rules",
            candidates=(candidate(),),
        ),
        reviews(ReviewStatus.PROPOSED),
    )

    assert result.deltas[0].delta_type == DeltaType.REMOVED


def test_unapproved_decision_is_not_used_as_current_state() -> None:
    result = compare_approved_decisions(
        TechnicalBaseline(project_id="project", baseline_id="base", name="Base"),
        DecisionEvaluationResult(
            project_id="project",
            rule_set_id="rules",
            candidates=(candidate(),),
        ),
        reviews(ReviewStatus.NEEDS_INFORMATION),
    )

    assert result.deltas == ()


def test_project_mismatch_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        compare_approved_decisions(
            TechnicalBaseline(project_id="a", baseline_id="base", name="Base"),
            DecisionEvaluationResult(project_id="b", rule_set_id="rules"),
            TechnicalReviewSet(project_id="a"),
        )


def test_numeric_baseline_and_decision_create_quantity_delta() -> None:
    from dataclasses import replace

    numeric_candidate = replace(
        candidate(conclusion="Fallback conclusion."),
        object_ref="AHU-03",
        property_name="air_velocity",
        value="8.0",
        unit="M/S",
        quantity=8.0,
    )
    baseline = TechnicalBaseline(
        project_id="project",
        baseline_id="base",
        name="Base",
        items=(
            BaselineItem(
                id="base:1",
                comparison_key="ventilation|airflow requirement",
                category="ventilation",
                title="Airflow requirement",
                value="5.0",
                unit="M/S",
                object_ref="AHU-03",
                property_name="air_velocity",
                value_kind=ValueKind.NUMBER,
                quantity=5.0,
            ),
        ),
    )

    result = compare_approved_decisions(
        baseline,
        DecisionEvaluationResult(
            project_id="project",
            rule_set_id="rules",
            candidates=(numeric_candidate,),
        ),
        reviews(),
    )

    delta = result.deltas[0]
    assert delta.baseline_quantity == 5.0
    assert delta.approved_quantity == 8.0
    assert delta.quantity_delta == 3.0
    assert delta.change_direction == ChangeDirection.INCREASE
    assert delta.object_ref == "AHU-03"
    assert delta.property_name == "air_velocity"
