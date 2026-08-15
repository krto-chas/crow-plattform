from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .decision_models import AuthorityPolicy, RoundingPolicy
from .decision_services import detect_conflicts
from .models import Claim
from .pipeline import DecisionPipelineResult, run_claim_to_estimate


@dataclass(frozen=True, slots=True)
class PricingInput:
    base_unit_cost: Decimal
    alternative_unit_cost: Decimal
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class BatchPipelineItem:
    conflict_key: tuple[str, str, str]
    result: DecisionPipelineResult


@dataclass(frozen=True, slots=True)
class BatchPipelineResult:
    items: tuple[BatchPipelineItem, ...]
    skipped_claim_ids: tuple[str, ...]


def run_batch_claim_to_estimate(
    claims: tuple[Claim, ...],
    policy: AuthorityPolicy,
    pricing_by_conflict_key: dict[tuple[str, str, str], PricingInput],
    rounding: RoundingPolicy,
) -> BatchPipelineResult:
    conflicts = detect_conflicts(claims)
    claims_by_id = {claim.id: claim for claim in claims}
    items: list[BatchPipelineItem] = []
    used_claim_ids: set[str] = set()

    for conflict in conflicts:
        pricing = pricing_by_conflict_key.get(conflict.conflict_key)
        if pricing is None:
            continue
        conflict_claims = tuple(claims_by_id[claim_id] for claim_id in conflict.claim_ids)
        result = run_claim_to_estimate(
            conflict_claims,
            policy,
            pricing.base_unit_cost,
            pricing.alternative_unit_cost,
            pricing.quantity,
            rounding,
        )
        items.append(BatchPipelineItem(conflict.conflict_key, result))
        used_claim_ids.update(conflict.claim_ids)

    skipped = tuple(sorted(claim.id for claim in claims if claim.id not in used_claim_ids))
    return BatchPipelineResult(
        items=tuple(sorted(items, key=lambda item: item.conflict_key)),
        skipped_claim_ids=skipped,
    )
