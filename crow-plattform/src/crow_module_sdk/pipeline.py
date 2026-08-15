from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal

from .decision_models import (
    AcceptedClaim,
    AtaOpportunity,
    AuthorityDecision,
    AuthorityPolicy,
    ClientQuestion,
    CommercialImpact,
    Conflict,
    EstimateLine,
    Reservation,
    RoundingPolicy,
    TechnicalDelta,
)
from .decision_services import (
    accept_claim,
    calculate_commercial_impact,
    calculate_technical_delta,
    create_ata_opportunity,
    detect_conflicts,
    export_client_question,
    export_estimate_line,
    export_reservation,
    resolve_authority,
)
from .invalidation import ComputationFingerprint, IdempotencyStore
from .models import Claim, Evidence


@dataclass(frozen=True, slots=True)
class DecisionPipelineResult:
    conflict: Conflict
    authority_decision: AuthorityDecision
    accepted_claim: AcceptedClaim | None
    technical_delta: TechnicalDelta | None
    commercial_impact: CommercialImpact | None
    ata_opportunity: AtaOpportunity | None
    estimate_line: EstimateLine | None
    client_question: ClientQuestion | None
    reservation: Reservation | None
    evidence: tuple[Evidence, ...]


def _collect_evidence(
    conflict: Conflict,
    authority_decision: AuthorityDecision,
    technical_delta: TechnicalDelta | None,
    commercial_impact: CommercialImpact | None,
) -> tuple[Evidence, ...]:
    items: list[Evidence] = []
    items.extend(conflict.evidence)
    items.extend(authority_decision.evidence)
    if technical_delta is not None:
        items.extend(technical_delta.evidence)
    if commercial_impact is not None:
        items.extend(commercial_impact.evidence)
    return tuple(sorted(items, key=lambda item: item.id))


def run_claim_to_estimate(
    claims: tuple[Claim, ...],
    policy: AuthorityPolicy,
    base_unit_cost: Decimal,
    alternative_unit_cost: Decimal,
    quantity: Decimal,
    rounding: RoundingPolicy,
) -> DecisionPipelineResult:
    conflicts = detect_conflicts(claims)
    if len(conflicts) != 1:
        raise ValueError("The reference pipeline requires exactly one conflict")
    conflict = conflicts[0]
    claims_by_id = {claim.id: claim for claim in claims}
    decision = resolve_authority(conflict, claims_by_id, policy)

    if decision.selected_claim_id is None:
        return DecisionPipelineResult(
            conflict,
            decision,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            _collect_evidence(conflict, decision, None, None),
        )

    accepted = accept_claim(decision, claims_by_id)
    alternatives = [claims_by_id[cid] for cid in decision.rejected_claim_ids]
    if len(alternatives) != 1:
        raise ValueError("The reference pipeline requires exactly one alternative claim")

    technical = calculate_technical_delta(accepted, alternatives[0])
    impact = calculate_commercial_impact(
        technical,
        base_unit_cost=base_unit_cost,
        alternative_unit_cost=alternative_unit_cost,
        quantity=quantity,
        rounding=rounding,
        pricing_trace_ids=("pricing:reference",),
    )
    opportunity = create_ata_opportunity(impact, title="Alternativt tekniskt utförande")
    estimate = export_estimate_line(opportunity, impact, "Kostnadsdelta för alternativt utförande")
    question = export_client_question(opportunity, "Klargörande av motstridiga handlingar")
    reservation = export_reservation(opportunity)

    return DecisionPipelineResult(
        conflict,
        decision,
        accepted,
        technical,
        impact,
        opportunity,
        estimate,
        question,
        reservation,
        _collect_evidence(conflict, decision, technical, impact),
    )


def run_claim_to_estimate_idempotent(
    store: IdempotencyStore,
    claims: tuple[Claim, ...],
    policy: AuthorityPolicy,
    base_unit_cost: Decimal,
    alternative_unit_cost: Decimal,
    quantity: Decimal,
    rounding: RoundingPolicy,
) -> DecisionPipelineResult:
    payload = {
        "claims": [asdict(claim) for claim in claims],
        "policy": asdict(policy),
        "base_unit_cost": base_unit_cost,
        "alternative_unit_cost": alternative_unit_cost,
        "quantity": quantity,
        "rounding": asdict(rounding),
    }
    fingerprint = ComputationFingerprint.from_payload(payload)
    cached = store.get(fingerprint)
    if cached is not None:
        if not isinstance(cached, DecisionPipelineResult):
            raise TypeError("Cached object has unexpected type")
        return cached

    result = run_claim_to_estimate(
        claims,
        policy,
        base_unit_cost,
        alternative_unit_cost,
        quantity,
        rounding,
    )
    stored = store.put(fingerprint, result)
    if not isinstance(stored, DecisionPipelineResult):
        raise TypeError("Stored object has unexpected type")
    return stored
