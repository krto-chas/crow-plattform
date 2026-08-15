from __future__ import annotations

import hashlib

from crow_commercial_impact import (
    CommercialImpact,
    CommercialImpactSet,
    PricingStatus,
)

from .models import (
    AdjustedCommercialImpact,
    AdjustedCommercialImpactSet,
    AdjustmentBase,
    AdjustmentType,
    AppliedAdjustment,
    CommercialAdjustmentProfile,
    CommercialAdjustmentRule,
)


def _normal(value: str | None) -> str:
    return (value or "").strip().casefold()


def _matches(rule: CommercialAdjustmentRule, impact: CommercialImpact) -> bool:
    if rule.categories:
        category = _normal(impact.description.split(":", 1)[0])
        if category not in {_normal(item) for item in rule.categories}:
            return False
    if rule.cost_types:
        current = impact.cost_type.value if impact.cost_type is not None else ""
        if _normal(current) not in {_normal(item) for item in rule.cost_types}:
            return False
    return True


def _adjustment_amount(
    rule: CommercialAdjustmentRule,
    net_amount: float,
    running_total: float,
) -> tuple[float, float | None, float]:
    base_amount = net_amount if rule.base == AdjustmentBase.NET_AMOUNT else running_total
    if rule.adjustment_type == AdjustmentType.PERCENTAGE:
        amount = base_amount * rule.value / 100.0
        rate = rule.value
    else:
        amount = rule.value
        rate = None
    return base_amount, rate, amount


def _fingerprint(
    impact_id: str,
    rule: CommercialAdjustmentRule,
    base_amount: float,
    amount: float,
) -> str:
    material = "|".join(
        (
            impact_id,
            rule.id,
            f"{base_amount:.12g}",
            f"{amount:.12g}",
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def apply_adjustments(
    commercial: CommercialImpactSet,
    profile: CommercialAdjustmentProfile,
) -> AdjustedCommercialImpactSet:
    if commercial.currency != profile.currency:
        raise ValueError("Commercial impacts and adjustment profile must use same currency")

    adjusted: list[AdjustedCommercialImpact] = []
    for impact in sorted(commercial.impacts, key=lambda item: item.id):
        if impact.pricing_status != PricingStatus.PRICED or impact.amount is None:
            continue

        net_amount = impact.amount
        running_total = net_amount
        applied: list[AppliedAdjustment] = []
        rules = sorted(
            (rule for rule in profile.rules if rule.enabled and _matches(rule, impact)),
            key=lambda item: (item.priority, item.id),
        )
        for rule in rules:
            base_amount, rate, amount = _adjustment_amount(
                rule,
                net_amount,
                running_total,
            )
            fingerprint = _fingerprint(impact.id, rule, base_amount, amount)
            applied.append(
                AppliedAdjustment(
                    id=f"commercial-adjustment:{fingerprint}",
                    rule_id=rule.id,
                    kind=rule.kind,
                    description=rule.name,
                    base_amount=base_amount,
                    rate=rate,
                    amount=amount,
                    currency=profile.currency,
                    fingerprint=fingerprint,
                )
            )
            running_total += amount

        adjusted.append(
            AdjustedCommercialImpact(
                commercial_impact_id=impact.id,
                description=impact.description,
                category=None,
                cost_type=impact.cost_type.value if impact.cost_type else None,
                net_amount=net_amount,
                adjustments=tuple(applied),
                adjusted_total=running_total,
                currency=profile.currency,
            )
        )

    return AdjustedCommercialImpactSet(
        project_id=commercial.project_id,
        baseline_id=commercial.baseline_id,
        source_price_book_id=commercial.price_book_id,
        adjustment_profile_id=profile.id,
        currency=profile.currency,
        impacts=tuple(adjusted),
        unresolved_count=commercial.unresolved_count,
    )
