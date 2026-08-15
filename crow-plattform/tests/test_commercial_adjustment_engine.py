from crow_commercial_adjustment import (
    AdjustmentBase,
    AdjustmentKind,
    AdjustmentType,
    CommercialAdjustmentProfile,
    CommercialAdjustmentRule,
    apply_adjustments,
)
from crow_commercial_impact import (
    CommercialImpact,
    CommercialImpactProvenance,
    CommercialImpactSet,
    CostType,
    PricingStatus,
)


def commercial_impact(amount: float = 1000.0) -> CommercialImpact:
    return CommercialImpact(
        id="commercial:1",
        scope_impact_id="scope:1",
        cost_type=CostType.LABOUR,
        description="Ventilation labour",
        quantity=1.0,
        unit="ST",
        unit_rate=amount,
        currency="SEK",
        amount=amount,
        pricing_status=PricingStatus.PRICED,
        requires_review=False,
        confidence=0.9,
        provenance=CommercialImpactProvenance(
            scope_impact_id="scope:1",
            technical_delta_id="delta:1",
            decision_id="decision:1",
            review_event_id="review:1",
            accepted_claim_ids=("accepted:1",),
            authority_decision_ids=("authority:1",),
            document_ids=("document:1",),
            scope_rule_id="scope-rule:1",
            price_book_id="book",
            unit_rate_id="rate:1",
            trace=("priced",),
        ),
        fingerprint="commercial-fingerprint",
    )


def profile() -> CommercialAdjustmentProfile:
    return CommercialAdjustmentProfile(
        id="profile",
        name="Profile",
        version="1",
        currency="SEK",
        rules=(
            CommercialAdjustmentRule(
                id="markup",
                name="Markup",
                kind=AdjustmentKind.MARKUP,
                adjustment_type=AdjustmentType.PERCENTAGE,
                base=AdjustmentBase.NET_AMOUNT,
                value=10.0,
                cost_types=("labour",),
                priority=100,
            ),
            CommercialAdjustmentRule(
                id="risk",
                name="Risk",
                kind=AdjustmentKind.RISK,
                adjustment_type=AdjustmentType.PERCENTAGE,
                base=AdjustmentBase.RUNNING_TOTAL,
                value=5.0,
                priority=200,
            ),
        ),
    )


def test_sequential_adjustments() -> None:
    result = apply_adjustments(
        CommercialImpactSet(
            project_id="project",
            baseline_id="baseline",
            price_book_id="book",
            currency="SEK",
            impacts=(commercial_impact(),),
        ),
        profile(),
    )

    item = result.impacts[0]
    assert item.net_amount == 1000.0
    assert item.adjustments[0].amount == 100.0
    assert item.adjustments[1].base_amount == 1100.0
    assert item.adjustments[1].amount == 55.0
    assert item.adjusted_total == 1155.0
    assert result.adjustment_total == 155.0
    assert result.grand_total == 1155.0


def test_fixed_negative_discount() -> None:
    discount = CommercialAdjustmentProfile(
        id="discount",
        name="Discount",
        version="1",
        currency="SEK",
        rules=(
            CommercialAdjustmentRule(
                id="discount",
                name="Discount",
                kind=AdjustmentKind.DISCOUNT,
                adjustment_type=AdjustmentType.FIXED_AMOUNT,
                base=AdjustmentBase.NET_AMOUNT,
                value=-100.0,
            ),
        ),
    )

    result = apply_adjustments(
        CommercialImpactSet(
            project_id="project",
            baseline_id="baseline",
            price_book_id="book",
            currency="SEK",
            impacts=(commercial_impact(),),
        ),
        discount,
    )

    assert result.impacts[0].adjusted_total == 900.0


def test_unresolved_items_are_not_adjusted() -> None:
    unresolved = commercial_impact()
    from dataclasses import replace

    unresolved = replace(
        unresolved,
        amount=None,
        pricing_status=PricingStatus.MISSING_UNIT_RATE,
        requires_review=True,
    )
    result = apply_adjustments(
        CommercialImpactSet(
            project_id="project",
            baseline_id="baseline",
            price_book_id="book",
            currency="SEK",
            impacts=(unresolved,),
        ),
        profile(),
    )

    assert result.impacts == ()
    assert result.unresolved_count == 1


def test_currency_mismatch_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        apply_adjustments(
            CommercialImpactSet(
                project_id="project",
                baseline_id="baseline",
                price_book_id="book",
                currency="EUR",
            ),
            profile(),
        )
