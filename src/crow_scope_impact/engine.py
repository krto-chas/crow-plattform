from __future__ import annotations

import hashlib

from crow_technical_delta import (
    ChangeDirection,
    DeltaType,
    TechnicalDelta,
    TechnicalDeltaSet,
)

from .models import (
    QuantityBasis,
    ScopeImpact,
    ScopeImpactProvenance,
    ScopeImpactRule,
    ScopeImpactRuleSet,
    ScopeImpactSet,
    ScopeImpactType,
)


def _normalized(value: str | None) -> str:
    return (value or "").strip().casefold()


def _matches(rule: ScopeImpactRule, delta: TechnicalDelta) -> bool:
    if rule.categories and _normalized(delta.category) not in {
        _normalized(item) for item in rule.categories
    }:
        return False
    if rule.property_names and _normalized(delta.property_name) not in {
        _normalized(item) for item in rule.property_names
    }:
        return False
    if rule.change_directions and delta.change_direction.value not in {
        _normalized(item) for item in rule.change_directions
    }:
        return False
    return True


def _quantity(rule: ScopeImpactRule, delta: TechnicalDelta) -> float | None:
    if rule.quantity_basis == QuantityBasis.DELTA_QUANTITY:
        value = delta.quantity_delta
    elif rule.quantity_basis == QuantityBasis.APPROVED_QUANTITY:
        value = delta.approved_quantity
    elif rule.quantity_basis == QuantityBasis.BASELINE_QUANTITY:
        value = delta.baseline_quantity
    elif rule.quantity_basis == QuantityBasis.FIXED:
        value = rule.fixed_quantity
    else:
        value = None
    return value * rule.multiplier if value is not None else None


def _default_impact(delta: TechnicalDelta) -> tuple[ScopeImpactType, bool]:
    if delta.delta_type == DeltaType.ADDED:
        return ScopeImpactType.ADDED_WORK, False
    if delta.delta_type == DeltaType.REMOVED:
        return ScopeImpactType.OMITTED_WORK, False
    if delta.delta_type == DeltaType.UNCHANGED:
        return ScopeImpactType.NO_SCOPE_CHANGE, False
    if delta.change_direction in {
        ChangeDirection.INCREASE,
        ChangeDirection.DECREASE,
        ChangeDirection.CHANGED,
    }:
        return ScopeImpactType.CHANGED_WORK, delta.quantity_delta is None
    return ScopeImpactType.REVIEW_REQUIRED, True


def _fingerprint(
    delta: TechnicalDelta,
    impact_type: ScopeImpactType,
    quantity: float | None,
    unit: str | None,
    rule_id: str | None,
) -> str:
    material = "|".join(
        (
            delta.id,
            impact_type.value,
            "" if quantity is None else f"{quantity:.12g}",
            unit or "",
            rule_id or "",
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _render_description(rule: ScopeImpactRule | None, delta: TechnicalDelta) -> str:
    template = rule.description_template if rule else "{title}"
    return template.format(
        title=delta.title,
        category=delta.category,
        object_ref=delta.object_ref or "",
        property_name=delta.property_name or "",
        baseline_value=delta.baseline_value or "",
        approved_value=delta.approved_value or "",
        unit=delta.unit or "",
    )


def derive_scope_impacts(
    deltas: TechnicalDeltaSet,
    rule_set: ScopeImpactRuleSet,
) -> ScopeImpactSet:
    impacts: list[ScopeImpact] = []

    for delta in sorted(deltas.deltas, key=lambda item: item.id):
        matched_rule = next(
            (
                rule
                for rule in sorted(
                    (item for item in rule_set.rules if item.enabled),
                    key=lambda item: (-item.priority, item.id),
                )
                if _matches(rule, delta)
            ),
            None,
        )

        if matched_rule is None:
            impact_type, requires_review = _default_impact(delta)
            quantity = abs(delta.quantity_delta) if delta.quantity_delta is not None else None
            unit = delta.unit
            rule_id = None
        else:
            impact_type = matched_rule.impact_type
            quantity = _quantity(matched_rule, delta)
            unit = matched_rule.output_unit or delta.unit
            rule_id = matched_rule.id
            requires_review = impact_type == ScopeImpactType.REVIEW_REQUIRED

        fingerprint = _fingerprint(delta, impact_type, quantity, unit, rule_id)
        impacts.append(
            ScopeImpact(
                id=f"scope-impact:{fingerprint}",
                impact_type=impact_type,
                category=delta.category,
                object_ref=delta.object_ref,
                property_name=delta.property_name,
                description=_render_description(matched_rule, delta),
                quantity=quantity,
                unit=unit,
                confidence=delta.confidence,
                requires_review=requires_review,
                provenance=ScopeImpactProvenance(
                    technical_delta_id=delta.id,
                    baseline_item_id=delta.provenance.baseline_item_id,
                    decision_id=delta.provenance.decision_id,
                    review_event_id=delta.provenance.review_event_id,
                    accepted_claim_ids=delta.provenance.accepted_claim_ids,
                    authority_decision_ids=delta.provenance.authority_decision_ids,
                    document_ids=delta.provenance.document_ids,
                    rule_id=rule_id,
                    rule_set_id=rule_set.id,
                    trace=(
                        f"Technical delta classified as {delta.delta_type.value}.",
                        (
                            f"Scope rule applied: {rule_id}"
                            if rule_id
                            else "No scope rule matched; deterministic default applied."
                        ),
                        f"Scope impact classified as {impact_type.value}.",
                    ),
                ),
                fingerprint=fingerprint,
            )
        )

    return ScopeImpactSet(
        project_id=deltas.project_id,
        baseline_id=deltas.baseline_id,
        rule_set_id=rule_set.id,
        impacts=tuple(impacts),
    )
