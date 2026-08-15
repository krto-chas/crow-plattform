from __future__ import annotations

import hashlib
import math

from crow_commercial_adjustment import AdjustedCommercialImpactSet
from crow_commercial_impact import CommercialImpactSet, PricingStatus
from crow_commercial_review import CommercialReview, CommercialReviewStatus

from .models import (
    Estimate,
    EstimateLine,
    EstimateLineProvenance,
    EstimateLineStatus,
)


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-6)


def _validate_inputs(
    commercial: CommercialImpactSet,
    adjusted: AdjustedCommercialImpactSet,
    review: CommercialReview,
) -> None:
    if review.status != CommercialReviewStatus.APPROVED:
        raise ValueError("Commercial review must be approved")
    if review.latest_event_id is None:
        raise ValueError("Approved commercial review must have an approval event")
    if review.unresolved_count != 0 or adjusted.unresolved_count != 0:
        raise ValueError("Estimate cannot be generated with unresolved commercial items")
    if len({commercial.project_id, adjusted.project_id, review.project_id}) != 1:
        raise ValueError("Project mismatch between commercial estimate inputs")
    if len({commercial.baseline_id, adjusted.baseline_id, review.baseline_id}) != 1:
        raise ValueError("Baseline mismatch between commercial estimate inputs")
    if commercial.price_book_id != adjusted.source_price_book_id:
        raise ValueError("Adjusted calculation references another price book")
    if commercial.price_book_id != review.source_price_book_id:
        raise ValueError("Commercial review references another price book")
    if adjusted.adjustment_profile_id != review.adjustment_profile_id:
        raise ValueError("Commercial review references another adjustment profile")
    if len({commercial.currency, adjusted.currency, review.currency}) != 1:
        raise ValueError("Currency mismatch between commercial estimate inputs")
    if not _close(adjusted.grand_total, review.grand_total):
        raise ValueError("Approved review total does not match adjusted calculation")


def _fingerprint(
    estimate_id: str,
    line_number: int,
    commercial_id: str,
    net_amount: float,
    total_amount: float,
    review_event_id: str,
) -> str:
    material = "|".join(
        (
            estimate_id,
            str(line_number),
            commercial_id,
            f"{net_amount:.12g}",
            f"{total_amount:.12g}",
            review_event_id,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def generate_estimate(
    commercial: CommercialImpactSet,
    adjusted: AdjustedCommercialImpactSet,
    review: CommercialReview,
    estimate_id: str,
) -> Estimate:
    _validate_inputs(commercial, adjusted, review)

    commercial_by_id = {item.id: item for item in commercial.impacts}
    adjusted_by_id = {item.commercial_impact_id: item for item in adjusted.impacts}
    priced_ids = {
        item.id for item in commercial.impacts if item.pricing_status == PricingStatus.PRICED
    }
    if priced_ids != set(adjusted_by_id):
        raise ValueError("Adjusted items must match all and only priced commercial impacts")

    review_event_id = review.latest_event_id
    assert review_event_id is not None

    lines: list[EstimateLine] = []
    for line_number, commercial_id in enumerate(sorted(priced_ids), start=1):
        source = commercial_by_id[commercial_id]
        adjusted_item = adjusted_by_id[commercial_id]
        if source.quantity is None or source.unit is None or source.unit_rate is None:
            raise ValueError(f"Priced commercial impact lacks line data: {source.id}")
        if source.amount is None:
            raise ValueError(f"Priced commercial impact lacks net amount: {source.id}")
        if not _close(source.amount, adjusted_item.net_amount):
            raise ValueError(f"Adjusted net amount mismatch: {source.id}")

        adjustment_amount = sum(adjustment.amount for adjustment in adjusted_item.adjustments)
        expected_total = adjusted_item.net_amount + adjustment_amount
        if not _close(expected_total, adjusted_item.adjusted_total):
            raise ValueError(f"Adjusted total is inconsistent: {source.id}")

        fingerprint = _fingerprint(
            estimate_id,
            line_number,
            source.id,
            source.amount,
            adjusted_item.adjusted_total,
            review_event_id,
        )
        lines.append(
            EstimateLine(
                id=f"estimate-line:{fingerprint}",
                line_number=line_number,
                status=EstimateLineStatus.READY,
                description=source.description,
                cost_type=source.cost_type.value if source.cost_type else None,
                quantity=source.quantity,
                unit=source.unit,
                unit_rate=source.unit_rate,
                net_amount=source.amount,
                adjustment_amount=adjustment_amount,
                total_amount=adjusted_item.adjusted_total,
                currency=source.currency,
                provenance=EstimateLineProvenance(
                    commercial_impact_id=source.id,
                    scope_impact_id=source.provenance.scope_impact_id,
                    technical_delta_id=source.provenance.technical_delta_id,
                    decision_id=source.provenance.decision_id,
                    review_event_id=source.provenance.review_event_id,
                    accepted_claim_ids=source.provenance.accepted_claim_ids,
                    authority_decision_ids=source.provenance.authority_decision_ids,
                    document_ids=source.provenance.document_ids,
                    scope_rule_id=source.provenance.scope_rule_id,
                    price_book_id=source.provenance.price_book_id,
                    unit_rate_id=source.provenance.unit_rate_id,
                    adjustment_profile_id=adjusted.adjustment_profile_id,
                    commercial_review_event_id=review_event_id,
                    adjustment_ids=tuple(adjustment.id for adjustment in adjusted_item.adjustments),
                    trace=(
                        f"Commercial impact: {source.id}",
                        f"Adjusted commercial impact: {adjusted_item.commercial_impact_id}",
                        f"Approved commercial review event: {review_event_id}",
                        f"Estimate line generated as line {line_number}.",
                    ),
                ),
                fingerprint=fingerprint,
            )
        )

    estimate = Estimate(
        project_id=commercial.project_id,
        baseline_id=commercial.baseline_id,
        estimate_id=estimate_id,
        currency=commercial.currency,
        price_book_id=commercial.price_book_id,
        adjustment_profile_id=adjusted.adjustment_profile_id,
        commercial_review_event_id=review_event_id,
        lines=tuple(lines),
    )
    if not _close(estimate.grand_total, review.grand_total):
        raise ValueError("Generated estimate total does not match approved review")
    return estimate
