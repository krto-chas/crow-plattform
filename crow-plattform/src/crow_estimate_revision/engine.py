from __future__ import annotations

import hashlib
import math
from dataclasses import asdict
from typing import Any

from crow_estimate_structure import BillOfQuantityLine, StructuredEstimate

from .models import (
    EstimateChangeType,
    EstimateFieldChange,
    EstimateLineChange,
    EstimateRevision,
)


def _hash(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()


def _lines(value: StructuredEstimate) -> dict[str, BillOfQuantityLine]:
    result: dict[str, BillOfQuantityLine] = {}
    for section in value.sections:
        for group in section.groups:
            for line in group.lines:
                if line.estimate_line_id in result:
                    raise ValueError(f"Duplicate estimate line identity: {line.estimate_line_id}")
                result[line.estimate_line_id] = line
    return result


def _field_changes(
    previous: BillOfQuantityLine,
    current: BillOfQuantityLine,
) -> tuple[EstimateFieldChange, ...]:
    comparable = (
        "position",
        "description",
        "quantity",
        "unit",
        "unit_rate",
        "net_amount",
        "adjustment_amount",
        "total_amount",
        "currency",
    )
    changes: list[EstimateFieldChange] = []
    previous_raw: dict[str, Any] = asdict(previous)
    current_raw: dict[str, Any] = asdict(current)
    for field in comparable:
        old = previous_raw[field]
        new = current_raw[field]
        if old != new:
            changes.append(EstimateFieldChange(field=field, previous=old, current=new))
    return tuple(changes)


def _explanation(
    change_type: EstimateChangeType,
    line_id: str,
    changes: tuple[EstimateFieldChange, ...],
) -> str:
    if change_type is EstimateChangeType.ADDED:
        return f"Estimate line {line_id} was added in the current revision."
    if change_type is EstimateChangeType.REMOVED:
        return f"Estimate line {line_id} was removed from the current revision."
    if change_type is EstimateChangeType.UNCHANGED:
        return f"Estimate line {line_id} is unchanged."
    fields = ", ".join(change.field for change in changes)
    return f"Estimate line {line_id} changed fields: {fields}."


def compare_estimates(
    previous: StructuredEstimate,
    current: StructuredEstimate,
    revision_id: str,
    *,
    include_unchanged: bool = False,
) -> EstimateRevision:
    if previous.project_id != current.project_id:
        raise ValueError("Project IDs must match")
    if previous.baseline_id != current.baseline_id:
        raise ValueError("Baseline IDs must match")
    if previous.currency != current.currency:
        raise ValueError("Currencies must match")

    previous_lines = _lines(previous)
    current_lines = _lines(current)
    changes: list[EstimateLineChange] = []

    for line_id in sorted(set(previous_lines) | set(current_lines)):
        old = previous_lines.get(line_id)
        new = current_lines.get(line_id)

        if old is None and new is not None:
            change_type = EstimateChangeType.ADDED
            field_changes: tuple[EstimateFieldChange, ...] = ()
            amount_delta = new.total_amount
        elif old is not None and new is None:
            change_type = EstimateChangeType.REMOVED
            field_changes = ()
            amount_delta = -old.total_amount
        elif old is not None and new is not None:
            field_changes = _field_changes(old, new)
            change_type = (
                EstimateChangeType.MODIFIED if field_changes else EstimateChangeType.UNCHANGED
            )
            amount_delta = new.total_amount - old.total_amount
        else:
            raise AssertionError("Unreachable line comparison state")

        if change_type is EstimateChangeType.UNCHANGED and not include_unchanged:
            continue

        previous_position = old.position if old is not None else None
        current_position = new.position if new is not None else None
        previous_fingerprint = old.fingerprint if old is not None else None
        current_fingerprint = new.fingerprint if new is not None else None
        explanation = _explanation(change_type, line_id, field_changes)
        fingerprint = _hash(
            revision_id,
            change_type.value,
            line_id,
            previous_fingerprint,
            current_fingerprint,
            *(f"{c.field}:{c.previous}->{c.current}" for c in field_changes),
            amount_delta,
        )
        changes.append(
            EstimateLineChange(
                id=f"estimate-line-change:{fingerprint}",
                change_type=change_type,
                estimate_line_id=line_id,
                previous_position=previous_position,
                current_position=current_position,
                previous_fingerprint=previous_fingerprint,
                current_fingerprint=current_fingerprint,
                field_changes=field_changes,
                explanation=explanation,
                amount_delta=amount_delta,
                fingerprint=fingerprint,
            )
        )

    previous_total = previous.grand_total
    current_total = current.grand_total
    total_delta = current_total - previous_total
    change_sum = sum(change.amount_delta for change in changes)
    if include_unchanged:
        change_sum = sum(
            change.amount_delta
            for change in changes
            if change.change_type is not EstimateChangeType.UNCHANGED
        )
    if not math.isclose(change_sum, total_delta, abs_tol=1e-6):
        raise ValueError("Revision line deltas do not reconcile to total delta")

    fingerprint = _hash(
        revision_id,
        previous.fingerprint,
        current.fingerprint,
        *(change.fingerprint for change in changes),
        previous_total,
        current_total,
        total_delta,
    )
    return EstimateRevision(
        id=revision_id,
        project_id=previous.project_id,
        baseline_id=previous.baseline_id,
        previous_estimate_id=previous.estimate_id,
        current_estimate_id=current.estimate_id,
        previous_structure_id=previous.structure_id,
        current_structure_id=current.structure_id,
        previous_fingerprint=previous.fingerprint,
        current_fingerprint=current.fingerprint,
        currency=current.currency,
        line_changes=tuple(changes),
        previous_total=previous_total,
        current_total=current_total,
        total_delta=total_delta,
        fingerprint=fingerprint,
    )
