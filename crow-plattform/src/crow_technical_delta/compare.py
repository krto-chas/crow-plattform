from __future__ import annotations

import hashlib

from crow_decision_engine import DecisionEvaluationResult, TechnicalDecisionCandidate
from crow_technical_review import (
    ReviewStatus,
    ReviewTargetType,
    TechnicalReviewSet,
)

from .models import (
    BaselineItem,
    DeltaType,
    TechnicalBaseline,
    TechnicalDelta,
    TechnicalDeltaProvenance,
    TechnicalDeltaSet,
    ValueKind,
)
from .semantics import structure_change


def decision_comparison_key(candidate: TechnicalDecisionCandidate) -> str:
    return "|".join(
        (
            candidate.category.strip().casefold(),
            candidate.title.strip().casefold(),
        )
    )


def _fingerprint(
    comparison_key: str,
    delta_type: DeltaType,
    baseline_value: str | None,
    approved_value: str | None,
    baseline_item_id: str | None,
    decision_id: str | None,
) -> str:
    material = "|".join(
        (
            comparison_key,
            delta_type.value,
            baseline_value or "",
            approved_value or "",
            baseline_item_id or "",
            decision_id or "",
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _delta(
    comparison_key: str,
    delta_type: DeltaType,
    category: str,
    title: str,
    baseline_value: str | None,
    approved_value: str | None,
    unit: str | None,
    baseline: BaselineItem | None,
    decision: TechnicalDecisionCandidate | None,
    review_event_id: str | None,
    object_ref: str | None,
    property_name: str | None,
    value_kind: ValueKind,
) -> TechnicalDelta:
    fingerprint = _fingerprint(
        comparison_key,
        delta_type,
        baseline_value,
        approved_value,
        baseline.id if baseline else None,
        decision.id if decision else None,
    )
    structured = structure_change(
        delta_type,
        baseline_value,
        approved_value,
        value_kind,
    )
    trace = (
        f"Baseline item: {baseline.id}" if baseline else "No baseline item matched.",
        f"Approved decision: {decision.id}" if decision else "No approved decision matched.",
        f"Delta classified as {delta_type.value}.",
    )
    return TechnicalDelta(
        id=f"technical-delta:{fingerprint}",
        comparison_key=comparison_key,
        delta_type=delta_type,
        category=category,
        title=title,
        baseline_value=baseline_value,
        approved_value=approved_value,
        unit=unit,
        confidence=decision.confidence if decision else None,
        provenance=TechnicalDeltaProvenance(
            baseline_item_id=baseline.id if baseline else None,
            decision_id=decision.id if decision else None,
            review_event_id=review_event_id,
            accepted_claim_ids=(decision.provenance.accepted_claim_ids if decision else ()),
            authority_decision_ids=(decision.provenance.authority_decision_ids if decision else ()),
            document_ids=decision.provenance.document_ids if decision else (),
            trace=trace,
        ),
        fingerprint=fingerprint,
        object_ref=object_ref,
        property_name=property_name,
        value_kind=value_kind,
        baseline_quantity=structured.baseline_quantity,
        approved_quantity=structured.approved_quantity,
        quantity_delta=structured.quantity_delta,
        change_direction=structured.direction,
    )


def compare_approved_decisions(
    baseline: TechnicalBaseline,
    decisions: DecisionEvaluationResult,
    reviews: TechnicalReviewSet,
) -> TechnicalDeltaSet:
    if len({baseline.project_id, decisions.project_id, reviews.project_id}) != 1:
        raise ValueError("Baseline, decisions and reviews must belong to the same project")

    decision_by_id = {candidate.id: candidate for candidate in decisions.candidates}
    approved: dict[str, tuple[TechnicalDecisionCandidate, str | None]] = {}
    for record in reviews.records:
        if record.target_type != ReviewTargetType.TECHNICAL_DECISION:
            continue
        if record.status != ReviewStatus.APPROVED:
            continue
        candidate = decision_by_id.get(record.target_id)
        if candidate is None:
            raise ValueError(f"Approved review references unknown decision: {record.target_id}")
        key = decision_comparison_key(candidate)
        if key in approved:
            raise ValueError(f"Several approved decisions share comparison key: {key}")
        approved[key] = (candidate, record.latest_event_id)

    baseline_by_key: dict[str, BaselineItem] = {}
    for item in baseline.items:
        key = item.comparison_key.strip().casefold()
        if key in baseline_by_key:
            raise ValueError(f"Duplicate baseline comparison key: {key}")
        baseline_by_key[key] = item

    deltas: list[TechnicalDelta] = []
    all_keys = sorted(set(baseline_by_key) | set(approved))
    for key in all_keys:
        base = baseline_by_key.get(key)
        approved_entry = approved.get(key)
        candidate = approved_entry[0] if approved_entry else None
        event_id = approved_entry[1] if approved_entry else None

        if base is None and candidate is not None:
            delta_type = DeltaType.ADDED
            baseline_value = None
            approved_value = candidate.value or candidate.conclusion
            category = candidate.category
            title = candidate.title
        elif base is not None and candidate is None:
            delta_type = DeltaType.REMOVED
            baseline_value = base.value
            approved_value = None
            category = base.category
            title = base.title
        elif base is not None and candidate is not None:
            baseline_value = base.value
            approved_value = candidate.value or candidate.conclusion
            category = candidate.category
            title = candidate.title
            delta_type = (
                DeltaType.UNCHANGED
                if baseline_value.strip().casefold() == approved_value.strip().casefold()
                else DeltaType.MODIFIED
            )
        else:
            continue

        deltas.append(
            _delta(
                comparison_key=key,
                delta_type=delta_type,
                category=category,
                title=title,
                baseline_value=baseline_value,
                approved_value=approved_value,
                unit=base.unit if base else None,
                baseline=base,
                decision=candidate,
                review_event_id=event_id,
                object_ref=(
                    candidate.object_ref
                    if candidate and candidate.object_ref
                    else base.object_ref
                    if base
                    else None
                ),
                property_name=(
                    candidate.property_name
                    if candidate and candidate.property_name
                    else base.property_name
                    if base
                    else None
                ),
                value_kind=(
                    base.value_kind
                    if base
                    else ValueKind.NUMBER
                    if candidate and candidate.quantity is not None
                    else ValueKind.TEXT
                ),
            )
        )

    return TechnicalDeltaSet(
        project_id=baseline.project_id,
        baseline_id=baseline.baseline_id,
        deltas=tuple(deltas),
    )
