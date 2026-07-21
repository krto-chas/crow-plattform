from __future__ import annotations

from dataclasses import dataclass

from .models import ChangeDirection, DeltaType, ValueKind


@dataclass(frozen=True, slots=True)
class StructuredChange:
    baseline_quantity: float | None
    approved_quantity: float | None
    quantity_delta: float | None
    direction: ChangeDirection


def parse_quantity(value: str | None, kind: ValueKind) -> float | None:
    if value is None or kind != ValueKind.NUMBER:
        return None
    return float(value.strip().replace(",", "."))


def classify_direction(
    delta_type: DeltaType,
    baseline_quantity: float | None,
    approved_quantity: float | None,
) -> ChangeDirection:
    if delta_type == DeltaType.ADDED:
        return ChangeDirection.ADDED
    if delta_type == DeltaType.REMOVED:
        return ChangeDirection.REMOVED
    if delta_type == DeltaType.UNCHANGED:
        return ChangeDirection.UNCHANGED
    if baseline_quantity is not None and approved_quantity is not None:
        if approved_quantity > baseline_quantity:
            return ChangeDirection.INCREASE
        if approved_quantity < baseline_quantity:
            return ChangeDirection.DECREASE
        return ChangeDirection.UNCHANGED
    return ChangeDirection.CHANGED


def structure_change(
    delta_type: DeltaType,
    baseline_value: str | None,
    approved_value: str | None,
    value_kind: ValueKind,
) -> StructuredChange:
    baseline_quantity = parse_quantity(baseline_value, value_kind)
    approved_quantity = parse_quantity(approved_value, value_kind)
    quantity_delta = (
        approved_quantity - baseline_quantity
        if baseline_quantity is not None and approved_quantity is not None
        else None
    )
    return StructuredChange(
        baseline_quantity=baseline_quantity,
        approved_quantity=approved_quantity,
        quantity_delta=quantity_delta,
        direction=classify_direction(
            delta_type,
            baseline_quantity,
            approved_quantity,
        ),
    )
