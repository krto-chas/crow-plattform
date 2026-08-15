from crow_commercial_impact import (
    CostType,
    PriceBook,
    PricingStatus,
    UnitRate,
    derive_commercial_impacts,
)
from crow_scope_impact import (
    ScopeImpact,
    ScopeImpactProvenance,
    ScopeImpactSet,
    ScopeImpactType,
)


def scope_impact(
    *,
    impact_type: ScopeImpactType = ScopeImpactType.CHANGED_WORK,
    quantity: float | None = 3.0,
    requires_review: bool = False,
) -> ScopeImpact:
    return ScopeImpact(
        id="scope-impact:1",
        impact_type=impact_type,
        category="ventilation",
        object_ref="AHU-03",
        property_name="air_velocity",
        description="Velocity adjustment",
        quantity=quantity,
        unit="M/S",
        confidence=0.9,
        requires_review=requires_review,
        provenance=ScopeImpactProvenance(
            technical_delta_id="delta:1",
            baseline_item_id="baseline:1",
            decision_id="decision:1",
            review_event_id="review:1",
            accepted_claim_ids=("accepted:1",),
            authority_decision_ids=("authority:1",),
            document_ids=("document:1",),
            rule_id="scope-rule:1",
            rule_set_id="scope-rules",
            trace=("scope",),
        ),
        fingerprint="scope-fingerprint",
    )


def price_book() -> PriceBook:
    return PriceBook(
        id="price-book",
        name="Price book",
        version="1",
        currency="SEK",
        rates=(
            UnitRate(
                id="rate:1",
                category="ventilation",
                property_name="air_velocity",
                impact_types=("changed_work",),
                cost_type=CostType.LABOUR,
                unit="M/S",
                currency="SEK",
                unit_rate=1250.0,
                description="Velocity adjustment labour",
                priority=100,
            ),
        ),
    )


def test_matching_rate_prices_scope_impact() -> None:
    result = derive_commercial_impacts(
        ScopeImpactSet(
            project_id="project",
            baseline_id="baseline",
            rule_set_id="scope-rules",
            impacts=(scope_impact(),),
        ),
        price_book(),
    )

    impact = result.impacts[0]
    assert impact.pricing_status == PricingStatus.PRICED
    assert impact.cost_type == CostType.LABOUR
    assert impact.quantity == 3.0
    assert impact.unit_rate == 1250.0
    assert impact.amount == 3750.0
    assert not impact.requires_review
    assert result.priced_total == 3750.0


def test_missing_rate_is_explicit() -> None:
    result = derive_commercial_impacts(
        ScopeImpactSet(
            project_id="project",
            baseline_id="baseline",
            rule_set_id="scope-rules",
            impacts=(scope_impact(),),
        ),
        PriceBook(
            id="empty",
            name="Empty",
            version="1",
            currency="SEK",
            rates=(),
        ),
    )

    impact = result.impacts[0]
    assert impact.pricing_status == PricingStatus.MISSING_UNIT_RATE
    assert impact.amount is None
    assert impact.requires_review


def test_missing_quantity_is_explicit() -> None:
    result = derive_commercial_impacts(
        ScopeImpactSet(
            project_id="project",
            baseline_id="baseline",
            rule_set_id="scope-rules",
            impacts=(scope_impact(quantity=None),),
        ),
        price_book(),
    )

    assert result.impacts[0].pricing_status == PricingStatus.MISSING_QUANTITY


def test_scope_review_requirement_blocks_pricing() -> None:
    result = derive_commercial_impacts(
        ScopeImpactSet(
            project_id="project",
            baseline_id="baseline",
            rule_set_id="scope-rules",
            impacts=(scope_impact(requires_review=True),),
        ),
        price_book(),
    )

    assert result.impacts[0].pricing_status == PricingStatus.REVIEW_REQUIRED
    assert result.impacts[0].amount is None


def test_no_scope_change_is_not_applicable() -> None:
    result = derive_commercial_impacts(
        ScopeImpactSet(
            project_id="project",
            baseline_id="baseline",
            rule_set_id="scope-rules",
            impacts=(
                scope_impact(
                    impact_type=ScopeImpactType.NO_SCOPE_CHANGE,
                    quantity=0.0,
                ),
            ),
        ),
        price_book(),
    )

    assert result.impacts[0].pricing_status == PricingStatus.NOT_APPLICABLE
    assert result.unresolved_count == 0
