from decimal import Decimal

from crow_module_sdk import (
    AuthorityPolicy,
    AuthorityRule,
    Claim,
    Provenance,
    RoundingPolicy,
    build_decision_graph,
)
from crow_module_sdk.pipeline import run_claim_to_estimate


def test_pipeline_is_automatically_connected_to_decision_graph() -> None:
    claims = (
        Claim(
            id="drawing-size",
            namespace="example",
            subject="COMPONENT-01",
            property="size",
            value=Decimal("160"),
            unit="mm",
            provenance=Provenance("DRAWING"),
        ),
        Claim(
            id="spec-size",
            namespace="example",
            subject="COMPONENT-01",
            property="size",
            value=Decimal("125"),
            unit="mm",
            provenance=Provenance("SPEC"),
        ),
    )
    policy = AuthorityPolicy(
        id="authority-2026",
        confirmed=True,
        rules=(AuthorityRule("AF-1.3", "SPEC", "DRAWING", "Specifikation före ritning."),),
    )
    result = run_claim_to_estimate(
        claims,
        policy,
        Decimal("500"),
        Decimal("684.20"),
        Decimal("100"),
        RoundingPolicy(),
    )

    graph = build_decision_graph(claims, result.conflict, result)

    assert result.estimate_line is not None
    trace = graph.trace_to(result.estimate_line.id)
    assert any(edge.source_id == "spec-size" for edge in trace)
    assert any(edge.target_id == result.commercial_impact.id for edge in trace)
