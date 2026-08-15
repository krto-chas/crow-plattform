from decimal import Decimal

from crow_module_sdk import (
    AuthorityPolicy,
    AuthorityRule,
    Claim,
    PricingInput,
    Provenance,
    RoundingPolicy,
    run_batch_claim_to_estimate,
)


def test_batch_pipeline_processes_multiple_conflicts() -> None:
    claims = (
        Claim(
            "drawing-size",
            "example",
            "COMPONENT-01",
            "size",
            Decimal("160"),
            "mm",
            Provenance("DRAWING"),
        ),
        Claim(
            "spec-size",
            "example",
            "COMPONENT-01",
            "size",
            Decimal("125"),
            "mm",
            Provenance("SPEC"),
        ),
        Claim(
            "drawing-count",
            "example",
            "COMPONENT-02",
            "count",
            Decimal("8"),
            "st",
            Provenance("DRAWING"),
        ),
        Claim(
            "spec-count",
            "example",
            "COMPONENT-02",
            "count",
            Decimal("10"),
            "st",
            Provenance("SPEC"),
        ),
        Claim(
            "unrelated",
            "example",
            "COMPONENT-03",
            "size",
            Decimal("50"),
            "mm",
            Provenance("SPEC"),
        ),
    )
    policy = AuthorityPolicy(
        id="authority-2026",
        confirmed=True,
        rules=(AuthorityRule("AF-1.3", "SPEC", "DRAWING", "Specifikation före ritning."),),
    )
    pricing = {
        ("example", "COMPONENT-01", "size"): PricingInput(
            Decimal("500"), Decimal("684.20"), Decimal("100")
        ),
        ("example", "COMPONENT-02", "count"): PricingInput(
            Decimal("1000"), Decimal("1250"), Decimal("2")
        ),
    }

    result = run_batch_claim_to_estimate(
        claims,
        policy,
        pricing,
        RoundingPolicy(),
    )

    assert len(result.items) == 2
    assert result.items[0].result.commercial_impact is not None
    assert result.items[1].result.commercial_impact is not None
    assert result.skipped_claim_ids == ("unrelated",)
