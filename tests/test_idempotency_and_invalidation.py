from decimal import Decimal

from crow_module_sdk import (
    AuthorityPolicy,
    AuthorityRule,
    Claim,
    IdempotencyStore,
    Provenance,
    RoundingPolicy,
    build_decision_graph,
    invalidate_from_source,
)
from crow_module_sdk.pipeline import run_claim_to_estimate_idempotent


def _fixture():
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
    return claims, policy


def test_repeated_pipeline_call_reuses_same_result() -> None:
    claims, policy = _fixture()
    store = IdempotencyStore()

    first = run_claim_to_estimate_idempotent(
        store,
        claims,
        policy,
        Decimal("500"),
        Decimal("684.20"),
        Decimal("100"),
        RoundingPolicy(),
    )
    second = run_claim_to_estimate_idempotent(
        store,
        claims,
        policy,
        Decimal("500"),
        Decimal("684.20"),
        Decimal("100"),
        RoundingPolicy(),
    )

    assert first is second
    assert store.size() == 1


def test_changed_source_invalidates_all_dependent_results() -> None:
    claims, policy = _fixture()
    store = IdempotencyStore()
    result = run_claim_to_estimate_idempotent(
        store,
        claims,
        policy,
        Decimal("500"),
        Decimal("684.20"),
        Decimal("100"),
        RoundingPolicy(),
    )
    graph = build_decision_graph(claims, result.conflict, result)

    invalidation = invalidate_from_source(graph, "spec-size")

    assert result.authority_decision.id in invalidation.invalidated_node_ids
    assert result.estimate_line is not None
    assert result.estimate_line.id in invalidation.invalidated_node_ids
