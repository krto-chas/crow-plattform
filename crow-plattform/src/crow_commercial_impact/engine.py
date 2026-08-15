from __future__ import annotations

import hashlib

from crow_scope_impact import ScopeImpact, ScopeImpactSet, ScopeImpactType

from .models import (
    CommercialImpact,
    CommercialImpactProvenance,
    CommercialImpactSet,
    PriceBook,
    PricingStatus,
    UnitRate,
)


def _normal(value: str | None) -> str:
    return (value or "").strip().casefold()


def _matches(rate: UnitRate, impact: ScopeImpact) -> bool:
    if _normal(rate.category) != _normal(impact.category):
        return False
    if rate.property_name is not None:
        if _normal(rate.property_name) != _normal(impact.property_name):
            return False
    if rate.impact_types:
        if impact.impact_type.value not in {_normal(item) for item in rate.impact_types}:
            return False
    if _normal(rate.unit) != _normal(impact.unit):
        return False
    return True


def _select_rate(price_book: PriceBook, impact: ScopeImpact) -> UnitRate | None:
    matches = [rate for rate in price_book.rates if rate.enabled and _matches(rate, impact)]
    if not matches:
        return None
    return sorted(matches, key=lambda item: (-item.priority, item.id))[0]


def _pricing_status(
    impact: ScopeImpact,
    rate: UnitRate | None,
) -> PricingStatus:
    if impact.impact_type == ScopeImpactType.NO_SCOPE_CHANGE:
        return PricingStatus.NOT_APPLICABLE
    if impact.requires_review or impact.impact_type == ScopeImpactType.REVIEW_REQUIRED:
        return PricingStatus.REVIEW_REQUIRED
    if impact.quantity is None:
        return PricingStatus.MISSING_QUANTITY
    if rate is None:
        return PricingStatus.MISSING_UNIT_RATE
    return PricingStatus.PRICED


def _fingerprint(
    impact: ScopeImpact,
    rate: UnitRate | None,
    status: PricingStatus,
    amount: float | None,
) -> str:
    material = "|".join(
        (
            impact.id,
            rate.id if rate else "",
            status.value,
            "" if amount is None else f"{amount:.12g}",
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def derive_commercial_impacts(
    scope_impacts: ScopeImpactSet,
    price_book: PriceBook,
) -> CommercialImpactSet:
    impacts: list[CommercialImpact] = []

    for scope in sorted(scope_impacts.impacts, key=lambda item: item.id):
        rate = _select_rate(price_book, scope)
        status = _pricing_status(scope, rate)
        amount = (
            scope.quantity * rate.unit_rate
            if status == PricingStatus.PRICED and scope.quantity is not None and rate is not None
            else None
        )
        fingerprint = _fingerprint(scope, rate, status, amount)
        impacts.append(
            CommercialImpact(
                id=f"commercial-impact:{fingerprint}",
                scope_impact_id=scope.id,
                cost_type=rate.cost_type if rate else None,
                description=(rate.description if rate is not None else scope.description),
                quantity=scope.quantity,
                unit=scope.unit,
                unit_rate=rate.unit_rate if rate else None,
                currency=price_book.currency,
                amount=amount,
                pricing_status=status,
                requires_review=status != PricingStatus.PRICED,
                confidence=scope.confidence,
                provenance=CommercialImpactProvenance(
                    scope_impact_id=scope.id,
                    technical_delta_id=scope.provenance.technical_delta_id,
                    decision_id=scope.provenance.decision_id,
                    review_event_id=scope.provenance.review_event_id,
                    accepted_claim_ids=scope.provenance.accepted_claim_ids,
                    authority_decision_ids=scope.provenance.authority_decision_ids,
                    document_ids=scope.provenance.document_ids,
                    scope_rule_id=scope.provenance.rule_id,
                    price_book_id=price_book.id,
                    unit_rate_id=rate.id if rate else None,
                    trace=(
                        f"Scope impact: {scope.id}",
                        (
                            f"Unit rate applied: {rate.id}"
                            if rate
                            else "No matching unit rate found."
                        ),
                        f"Pricing status: {status.value}",
                    ),
                ),
                fingerprint=fingerprint,
            )
        )

    return CommercialImpactSet(
        project_id=scope_impacts.project_id,
        baseline_id=scope_impacts.baseline_id,
        price_book_id=price_book.id,
        currency=price_book.currency,
        impacts=tuple(impacts),
    )
