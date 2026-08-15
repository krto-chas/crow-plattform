from decimal import Decimal

import pytest

from crow_module_sdk import (
    AuthorityPolicy,
    AuthorityRule,
    Claim,
    Provenance,
    ReviewStatus,
    RoundingPolicy,
)
from crow_module_sdk.decision_services import (
    InvalidAuthorityPolicy,
    accept_claim,
    calculate_commercial_impact,
    calculate_technical_delta,
    detect_conflicts,
    resolve_authority,
    validate_authority_policy,
)


def make_claim(claim_id: str, document: str, value: str) -> Claim:
    return Claim(
        id=claim_id,
        namespace="example",
        subject="COMPONENT-01",
        property="size",
        value=Decimal(value),
        unit="mm",
        provenance=Provenance(document_id=document, revision="A", page=1),
    )


def test_conflict_and_confirmed_authority_decision() -> None:
    drawing = make_claim("claim-drawing", "DRAWING", "160")
    specification = make_claim("claim-spec", "SPEC", "125")
    conflict = detect_conflicts((drawing, specification))[0]
    policy = AuthorityPolicy(
        id="policy-1",
        confirmed=True,
        rules=(AuthorityRule("AF-1.3", "SPEC", "DRAWING", "Beskrivning gäller före ritning."),),
    )

    decision = resolve_authority(conflict, {c.id: c for c in (drawing, specification)}, policy)

    assert decision.status is ReviewStatus.AUTOMATED
    assert decision.selected_claim_id == "claim-spec"
    assert decision.rule_id == "AF-1.3"


def test_unconfirmed_policy_requires_human_review() -> None:
    drawing = make_claim("claim-drawing", "DRAWING", "160")
    specification = make_claim("claim-spec", "SPEC", "125")
    conflict = detect_conflicts((drawing, specification))[0]
    policy = AuthorityPolicy(
        id="policy-1",
        confirmed=False,
        rules=(AuthorityRule("AF-1.3", "SPEC", "DRAWING", "Beskrivning gäller före ritning."),),
    )

    decision = resolve_authority(conflict, {c.id: c for c in (drawing, specification)}, policy)

    assert decision.status is ReviewStatus.HUMAN_REVIEW
    assert decision.selected_claim_id is None


def test_invalid_authority_cycle_is_rejected() -> None:
    policy = AuthorityPolicy(
        id="bad",
        confirmed=True,
        rules=(
            AuthorityRule("r1", "A", "B", "A före B"),
            AuthorityRule("r2", "B", "C", "B före C"),
            AuthorityRule("r3", "C", "A", "C före A"),
        ),
    )
    with pytest.raises(InvalidAuthorityPolicy):
        validate_authority_policy(policy)


def test_technical_and_commercial_delta_use_decimal_rounding() -> None:
    drawing = make_claim("claim-drawing", "DRAWING", "160")
    specification = make_claim("claim-spec", "SPEC", "125")
    conflict = detect_conflicts((drawing, specification))[0]
    policy = AuthorityPolicy(
        id="policy-1",
        confirmed=True,
        rules=(AuthorityRule("AF-1.3", "SPEC", "DRAWING", "Beskrivning gäller före ritning."),),
    )
    decision = resolve_authority(conflict, {c.id: c for c in (drawing, specification)}, policy)
    accepted = accept_claim(decision, {c.id: c for c in (drawing, specification)})
    technical = calculate_technical_delta(accepted, drawing)
    impact = calculate_commercial_impact(
        technical,
        base_unit_cost=Decimal("100.005"),
        alternative_unit_cost=Decimal("125.005"),
        quantity=Decimal("2"),
        rounding=RoundingPolicy(),
        pricing_trace_ids=("price-1",),
    )

    assert technical.absolute_delta == Decimal("35")
    assert impact.base_amount == Decimal("200.01")
    assert impact.alternative_amount == Decimal("250.01")
    assert impact.delta_amount == Decimal("50.00")


def test_numerically_equal_values_are_not_conflicts() -> None:
    from decimal import Decimal

    from crow_module_sdk import Claim, Provenance
    from crow_module_sdk.decision_services import detect_conflicts

    base = dict(namespace="vent", subject="duct", property="flow", unit="l/s")
    claims = (
        Claim(id="a", value=Decimal("1.0"), provenance=Provenance("d1"), **base),
        Claim(id="b", value=Decimal("1.00"), provenance=Provenance("d2"), **base),
        Claim(id="c", value=1.0, provenance=Provenance("d3"), **base),
    )
    assert detect_conflicts(claims) == ()

    conflicting = claims + (
        Claim(id="d", value=Decimal("2.0"), provenance=Provenance("d4"), **base),
    )
    assert len(detect_conflicts(conflicting)) == 1
