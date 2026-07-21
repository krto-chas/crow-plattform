from dataclasses import replace
from datetime import UTC, datetime

import pytest

from crow_commercial_adjustment import (
    AdjustedCommercialImpact,
    AdjustedCommercialImpactSet,
    AdjustmentKind,
    AppliedAdjustment,
)
from crow_commercial_impact import (
    CommercialImpact,
    CommercialImpactProvenance,
    CommercialImpactSet,
    CostType,
    PricingStatus,
)
from crow_commercial_review import (
    CommercialReviewStatus,
    initialize_commercial_review,
    transition_commercial_review,
)
from crow_estimate_line import generate_estimate


def commercial() -> CommercialImpactSet:
    impact = CommercialImpact(
        id="commercial:1",
        scope_impact_id="scope:1",
        cost_type=CostType.LABOUR,
        description="Ventilation adjustment",
        quantity=3.0,
        unit="M/S",
        unit_rate=1000.0,
        currency="SEK",
        amount=3000.0,
        pricing_status=PricingStatus.PRICED,
        requires_review=False,
        confidence=0.9,
        provenance=CommercialImpactProvenance(
            scope_impact_id="scope:1",
            technical_delta_id="delta:1",
            decision_id="decision:1",
            review_event_id="technical-review:1",
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
    return CommercialImpactSet(
        project_id="project",
        baseline_id="baseline",
        price_book_id="book",
        currency="SEK",
        impacts=(impact,),
    )


def adjusted(unresolved: int = 0) -> AdjustedCommercialImpactSet:
    adjustment = AppliedAdjustment(
        id="adjustment:1",
        rule_id="markup",
        kind=AdjustmentKind.MARKUP,
        description="Markup",
        base_amount=3000.0,
        rate=10.0,
        amount=300.0,
        currency="SEK",
        fingerprint="adjustment-fingerprint",
    )
    impact = AdjustedCommercialImpact(
        commercial_impact_id="commercial:1",
        description="Ventilation adjustment",
        category=None,
        cost_type="labour",
        net_amount=3000.0,
        adjustments=(adjustment,),
        adjusted_total=3300.0,
        currency="SEK",
    )
    return AdjustedCommercialImpactSet(
        project_id="project",
        baseline_id="baseline",
        source_price_book_id="book",
        adjustment_profile_id="profile",
        currency="SEK",
        impacts=(impact,),
        unresolved_count=unresolved,
    )


def approved_review():
    review = initialize_commercial_review(adjusted())
    return transition_commercial_review(
        review,
        CommercialReviewStatus.APPROVED,
        "Commercial Manager",
        "Approved estimate basis.",
        datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
    )


def test_generate_estimate_line_from_approved_commercial_basis() -> None:
    estimate = generate_estimate(
        commercial(),
        adjusted(),
        approved_review(),
        "estimate:001",
    )

    assert len(estimate.lines) == 1
    line = estimate.lines[0]
    assert line.line_number == 1
    assert line.quantity == 3.0
    assert line.unit_rate == 1000.0
    assert line.net_amount == 3000.0
    assert line.adjustment_amount == 300.0
    assert line.total_amount == 3300.0
    assert estimate.grand_total == 3300.0
    assert line.provenance.commercial_review_event_id


def test_unapproved_review_blocks_generation() -> None:
    review = initialize_commercial_review(adjusted())

    with pytest.raises(ValueError):
        generate_estimate(commercial(), adjusted(), review, "estimate:001")


def test_total_mismatch_blocks_generation() -> None:
    review = replace(approved_review(), grand_total=9999.0)

    with pytest.raises(ValueError):
        generate_estimate(commercial(), adjusted(), review, "estimate:001")


def test_unresolved_items_block_generation() -> None:
    review = replace(approved_review(), unresolved_count=1)

    with pytest.raises(ValueError):
        generate_estimate(
            commercial(),
            replace(adjusted(), unresolved_count=1),
            review,
            "estimate:001",
        )


def test_adjusted_items_must_match_priced_items() -> None:
    empty_adjusted = replace(adjusted(), impacts=())

    with pytest.raises(ValueError):
        generate_estimate(
            commercial(),
            empty_adjusted,
            approved_review(),
            "estimate:001",
        )


def test_line_number_and_fingerprint_are_deterministic() -> None:
    first = generate_estimate(
        commercial(),
        adjusted(),
        approved_review(),
        "estimate:001",
    )
    second = generate_estimate(
        commercial(),
        adjusted(),
        approved_review(),
        "estimate:001",
    )

    assert first.lines[0].id == second.lines[0].id
    assert first.lines[0].fingerprint == second.lines[0].fingerprint
