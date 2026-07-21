from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .decision_models import (
    AcceptedClaim,
    AtaOpportunity,
    AuthorityDecision,
    AuthorityPolicy,
    ClientQuestion,
    CommercialImpact,
    CommercialTreatment,
    Conflict,
    EstimateLine,
    OpportunityStatus,
    Reservation,
    ReviewStatus,
    RoundingPolicy,
    TechnicalDelta,
)
from .models import Claim, Evidence


class InvalidAuthorityPolicy(ValueError):
    pass


def _canonical_value(value: object) -> str:
    """Normalise a claim value for conflict comparison.

    Numerically equal values must not be flagged as conflicting, so numeric
    types (Decimal, int, float) are collapsed onto a canonical Decimal string:
    Decimal("1.0"), Decimal("1.00"), 1 and 1.0 all compare equal, while bools
    and non-numeric values fall back to repr().
    """
    if isinstance(value, bool):
        return repr(value)
    if isinstance(value, Decimal):
        return "num:" + str(value.normalize())
    if isinstance(value, int):
        return "num:" + str(Decimal(value).normalize())
    if isinstance(value, float):
        return "num:" + str(Decimal(str(value)).normalize())
    return repr(value)


def detect_conflicts(claims: tuple[Claim, ...]) -> tuple[Conflict, ...]:
    grouped: dict[tuple[str, str, str], list[Claim]] = defaultdict(list)
    for claim in claims:
        grouped[claim.conflict_key].append(claim)

    conflicts: list[Conflict] = []
    for key, items in sorted(grouped.items()):
        unique_values = {(_canonical_value(item.value), item.unit) for item in items}
        if len(items) > 1 and len(unique_values) > 1:
            claim_ids = tuple(sorted(item.id for item in items))
            conflicts.append(
                Conflict(
                    id="conflict:" + ":".join(key),
                    conflict_key=key,
                    claim_ids=claim_ids,
                    evidence=(
                        Evidence(
                            id="evidence:conflict:" + ":".join(key),
                            kind="observation",
                            statement="Oförenliga källpåståenden beskriver samma egenskap.",
                            source_claim_ids=claim_ids,
                        ),
                    ),
                )
            )
    return tuple(conflicts)


def validate_authority_policy(policy: AuthorityPolicy) -> None:
    edges = {(rule.higher_document_id, rule.lower_document_id) for rule in policy.rules}
    if any(high == low for high, low in edges):
        raise InvalidAuthorityPolicy("A document cannot outrank itself")
    if any((low, high) in edges for high, low in edges):
        raise InvalidAuthorityPolicy("Contradictory authority rules")

    graph: dict[str, set[str]] = defaultdict(set)
    for high, low in edges:
        graph[high].add(low)

    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(node: str) -> None:
        if node in visiting:
            raise InvalidAuthorityPolicy("Authority policy contains a cycle")
        if node in visited:
            return
        visiting.add(node)
        for child in graph.get(node, set()):
            walk(child)
        visiting.remove(node)
        visited.add(node)

    for node in tuple(graph):
        walk(node)


def resolve_authority(
    conflict: Conflict,
    claims_by_id: dict[str, Claim],
    policy: AuthorityPolicy,
) -> AuthorityDecision:
    validate_authority_policy(policy)
    claims = [claims_by_id[claim_id] for claim_id in conflict.claim_ids]

    if not policy.confirmed:
        return AuthorityDecision(
            id=f"authority:{conflict.id}",
            conflict_id=conflict.id,
            selected_claim_id=None,
            rejected_claim_ids=(),
            rule_id=None,
            status=ReviewStatus.HUMAN_REVIEW,
            evidence=(
                Evidence(
                    id=f"evidence:authority-review:{conflict.id}",
                    kind="rule",
                    statement="Dokumentordningen är inte bekräftad; mänsklig granskning krävs.",
                    source_claim_ids=conflict.claim_ids,
                ),
            ),
        )

    for rule in policy.rules:
        higher = [c for c in claims if c.provenance.document_id == rule.higher_document_id]
        lower = [c for c in claims if c.provenance.document_id == rule.lower_document_id]
        if higher and lower:
            selected = sorted(higher, key=lambda c: c.id)[0]
            rejected = tuple(sorted(c.id for c in claims if c.id != selected.id))
            return AuthorityDecision(
                id=f"authority:{conflict.id}",
                conflict_id=conflict.id,
                selected_claim_id=selected.id,
                rejected_claim_ids=rejected,
                rule_id=rule.id,
                status=ReviewStatus.AUTOMATED,
                evidence=(
                    Evidence(
                        id=f"evidence:authority:{conflict.id}",
                        kind="rule",
                        statement=rule.description,
                        source_claim_ids=conflict.claim_ids,
                        rule_id=rule.id,
                    ),
                ),
            )

    return AuthorityDecision(
        id=f"authority:{conflict.id}",
        conflict_id=conflict.id,
        selected_claim_id=None,
        rejected_claim_ids=(),
        rule_id=None,
        status=ReviewStatus.HUMAN_REVIEW,
        evidence=(
            Evidence(
                id=f"evidence:authority-unresolved:{conflict.id}",
                kind="conclusion",
                statement="Ingen tillämplig dokumentauktoritetsregel hittades.",
                source_claim_ids=conflict.claim_ids,
            ),
        ),
    )


def accept_claim(decision: AuthorityDecision, claims_by_id: dict[str, Claim]) -> AcceptedClaim:
    if decision.selected_claim_id is None:
        raise ValueError("Cannot create AcceptedClaim from an unresolved decision")
    return AcceptedClaim(
        id=f"accepted:{decision.selected_claim_id}",
        claim=claims_by_id[decision.selected_claim_id],
        authority_decision_id=decision.id,
    )


def calculate_technical_delta(
    accepted: AcceptedClaim,
    alternative: Claim,
) -> TechnicalDelta:
    if accepted.claim.conflict_key != alternative.conflict_key:
        raise ValueError("Claims must describe the same subject and property")
    if not isinstance(accepted.claim.value, Decimal) or not isinstance(alternative.value, Decimal):
        raise TypeError("Technical delta values must use Decimal")
    if accepted.claim.unit != alternative.unit or accepted.claim.unit is None:
        raise ValueError("Technical delta requires equal explicit units")
    delta = alternative.value - accepted.claim.value
    return TechnicalDelta(
        id=f"technical-delta:{accepted.claim.id}:{alternative.id}",
        subject=accepted.claim.subject,
        property=accepted.claim.property,
        accepted_value=accepted.claim.value,
        alternative_value=alternative.value,
        unit=accepted.claim.unit,
        absolute_delta=delta,
        evidence=(
            Evidence(
                id=f"evidence:technical-delta:{accepted.claim.id}:{alternative.id}",
                kind="calculation",
                statement=(
                    f"Alternativt värde {alternative.value} {alternative.unit} jämfört med "
                    f"styrande värde {accepted.claim.value} {accepted.claim.unit}."
                ),
                source_claim_ids=(accepted.claim.id, alternative.id),
            ),
        ),
    )


def calculate_commercial_impact(
    technical_delta: TechnicalDelta,
    base_unit_cost: Decimal,
    alternative_unit_cost: Decimal,
    quantity: Decimal,
    rounding: RoundingPolicy,
    pricing_trace_ids: tuple[str, ...],
    currency: str = "SEK",
) -> CommercialImpact:
    base = rounding.apply(base_unit_cost * quantity)
    alternative = rounding.apply(alternative_unit_cost * quantity)
    delta = rounding.apply(alternative - base)
    return CommercialImpact(
        id=f"commercial-impact:{technical_delta.id}",
        technical_delta_id=technical_delta.id,
        base_amount=base,
        alternative_amount=alternative,
        delta_amount=delta,
        currency=currency,
        pricing_trace_ids=pricing_trace_ids,
        evidence=(
            Evidence(
                id=f"evidence:commercial-impact:{technical_delta.id}",
                kind="calculation",
                statement=f"Prisskillnaden är {delta} {currency} efter avrundningspolicy.",
            ),
        ),
    )


def create_ata_opportunity(
    impact: CommercialImpact,
    title: str,
    treatment: CommercialTreatment = CommercialTreatment.PRICED_OPTION,
) -> AtaOpportunity:
    return AtaOpportunity(
        id=f"ata:{impact.id}",
        commercial_impact_id=impact.id,
        treatment=treatment,
        status=OpportunityStatus.IDENTIFIED,
        title=title,
        rationale=(
            f"Identifierad dokumentkonflikt med kommersiellt delta "
            f"{impact.delta_amount} {impact.currency}."
        ),
    )


def export_estimate_line(
    opportunity: AtaOpportunity,
    impact: CommercialImpact,
    description: str,
) -> EstimateLine:
    return EstimateLine(
        id=f"estimate:{opportunity.id}",
        description=description,
        quantity=Decimal("1"),
        unit="st",
        unit_price=impact.delta_amount,
        total=impact.delta_amount,
        currency=impact.currency,
        source_opportunity_id=opportunity.id,
    )


def export_client_question(opportunity: AtaOpportunity, subject: str) -> ClientQuestion:
    return ClientQuestion(
        id=f"question:{opportunity.id}",
        subject=subject,
        body=(
            f"Projektunderlaget innehåller en motstridighet kopplad till '{opportunity.title}'. "
            "Vänligen bekräfta vilket utförande som ska ligga till grund för anbud och produktion."
        ),
        source_opportunity_id=opportunity.id,
    )


def export_reservation(opportunity: AtaOpportunity) -> Reservation:
    return Reservation(
        id=f"reservation:{opportunity.id}",
        body=(
            f"Reservation görs för '{opportunity.title}' till dess att motstridigheten i "
            "projektunderlaget har klarlagts skriftligen."
        ),
        source_opportunity_id=opportunity.id,
    )
