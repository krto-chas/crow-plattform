from crow_scope_impact import (
    QuantityBasis,
    ScopeImpactRule,
    ScopeImpactRuleSet,
    ScopeImpactType,
    derive_scope_impacts,
)
from crow_technical_delta import (
    ChangeDirection,
    DeltaType,
    TechnicalDelta,
    TechnicalDeltaProvenance,
    TechnicalDeltaSet,
    ValueKind,
)


def delta(
    *,
    delta_type: DeltaType = DeltaType.MODIFIED,
    direction: ChangeDirection = ChangeDirection.INCREASE,
    quantity_delta: float | None = 3.0,
) -> TechnicalDelta:
    return TechnicalDelta(
        id="technical-delta:1",
        comparison_key="ventilation|velocity",
        delta_type=delta_type,
        category="ventilation",
        title="Velocity changed",
        baseline_value="5.0",
        approved_value="8.0",
        unit="M/S",
        confidence=0.9,
        provenance=TechnicalDeltaProvenance(
            baseline_item_id="baseline:1",
            decision_id="decision:1",
            review_event_id="review:1",
            accepted_claim_ids=("accepted:1",),
            authority_decision_ids=("authority:1",),
            document_ids=("document:1",),
            trace=("delta",),
        ),
        fingerprint="delta-fingerprint",
        object_ref="AHU-03",
        property_name="air_velocity",
        value_kind=ValueKind.NUMBER,
        baseline_quantity=5.0,
        approved_quantity=8.0,
        quantity_delta=quantity_delta,
        change_direction=direction,
    )


def rule_set() -> ScopeImpactRuleSet:
    return ScopeImpactRuleSet(
        id="scope-rules",
        name="Scope rules",
        version="1",
        rules=(
            ScopeImpactRule(
                id="velocity",
                name="Velocity",
                categories=("ventilation",),
                property_names=("air_velocity",),
                change_directions=("increase", "decrease"),
                impact_type=ScopeImpactType.CHANGED_WORK,
                quantity_basis=QuantityBasis.DELTA_QUANTITY,
                output_unit="M/S",
                description_template="{object_ref}: {property_name}",
                priority=100,
            ),
        ),
    )


def test_matching_rule_creates_quantified_scope_impact() -> None:
    result = derive_scope_impacts(
        TechnicalDeltaSet(
            project_id="project",
            baseline_id="baseline",
            deltas=(delta(),),
        ),
        rule_set(),
    )

    impact = result.impacts[0]
    assert impact.impact_type == ScopeImpactType.CHANGED_WORK
    assert impact.quantity == 3.0
    assert impact.unit == "M/S"
    assert impact.description == "AHU-03: air_velocity"
    assert impact.provenance.rule_id == "velocity"


def test_removed_delta_defaults_to_omitted_work() -> None:
    result = derive_scope_impacts(
        TechnicalDeltaSet(
            project_id="project",
            baseline_id="baseline",
            deltas=(
                delta(
                    delta_type=DeltaType.REMOVED,
                    direction=ChangeDirection.REMOVED,
                    quantity_delta=None,
                ),
            ),
        ),
        ScopeImpactRuleSet(id="rules", name="Rules", version="1", rules=()),
    )

    assert result.impacts[0].impact_type == ScopeImpactType.OMITTED_WORK


def test_textual_modified_delta_requires_review_without_rule() -> None:
    result = derive_scope_impacts(
        TechnicalDeltaSet(
            project_id="project",
            baseline_id="baseline",
            deltas=(
                delta(
                    delta_type=DeltaType.MODIFIED,
                    direction=ChangeDirection.CHANGED,
                    quantity_delta=None,
                ),
            ),
        ),
        ScopeImpactRuleSet(id="rules", name="Rules", version="1", rules=()),
    )

    assert result.impacts[0].impact_type == ScopeImpactType.CHANGED_WORK
    assert result.impacts[0].requires_review
    assert result.review_required_count == 1


def test_fixed_quantity_rule() -> None:
    rules = ScopeImpactRuleSet(
        id="rules",
        name="Rules",
        version="1",
        rules=(
            ScopeImpactRule(
                id="fixed",
                name="Fixed",
                categories=("ventilation",),
                property_names=("air_velocity",),
                change_directions=("increase",),
                impact_type=ScopeImpactType.ADDED_WORK,
                quantity_basis=QuantityBasis.FIXED,
                output_unit="ST",
                fixed_quantity=2.0,
            ),
        ),
    )

    result = derive_scope_impacts(
        TechnicalDeltaSet(
            project_id="project",
            baseline_id="baseline",
            deltas=(delta(),),
        ),
        rules,
    )

    assert result.impacts[0].quantity == 2.0
    assert result.impacts[0].unit == "ST"
