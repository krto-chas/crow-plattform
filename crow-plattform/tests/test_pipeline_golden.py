from decimal import Decimal

from crow_module_sdk import AuthorityPolicy, AuthorityRule, Claim, Provenance, RoundingPolicy
from crow_module_sdk.pipeline import run_claim_to_estimate


def test_claim_to_estimate_golden_flow() -> None:
    claims = (
        Claim(
            id="drawing-size",
            namespace="example",
            subject="COMPONENT-01",
            property="size",
            value=Decimal("160"),
            unit="mm",
            provenance=Provenance("DRAWING", "B", 4, "Section A-A"),
        ),
        Claim(
            id="spec-size",
            namespace="example",
            subject="COMPONENT-01",
            property="size",
            value=Decimal("125"),
            unit="mm",
            provenance=Provenance("SPEC", "B", 7, "3.2"),
        ),
    )
    policy = AuthorityPolicy(
        id="authority-2026",
        confirmed=True,
        rules=(AuthorityRule("AF-1.3", "SPEC", "DRAWING", "Beskrivning gäller före ritning."),),
    )

    result = run_claim_to_estimate(
        claims,
        policy,
        base_unit_cost=Decimal("500"),
        alternative_unit_cost=Decimal("684.20"),
        quantity=Decimal("100"),
        rounding=RoundingPolicy(),
    )

    assert result.accepted_claim is not None
    assert result.accepted_claim.claim.id == "spec-size"
    assert result.technical_delta is not None
    assert result.technical_delta.absolute_delta == Decimal("35")
    assert result.commercial_impact is not None
    assert result.commercial_impact.delta_amount == Decimal("18420.00")
    assert result.estimate_line is not None
    assert result.estimate_line.total == Decimal("18420.00")
    assert result.client_question is not None
    assert result.reservation is not None
