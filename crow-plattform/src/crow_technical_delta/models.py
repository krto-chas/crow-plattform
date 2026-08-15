from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DeltaType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


class ValueKind(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"


class ChangeDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    CHANGED = "changed"
    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class BaselineItem:
    id: str
    comparison_key: str
    category: str
    title: str
    value: str
    unit: str | None = None
    source: str = "baseline"
    object_ref: str | None = None
    property_name: str | None = None
    value_kind: ValueKind = ValueKind.TEXT
    quantity: float | None = None


@dataclass(frozen=True, slots=True)
class TechnicalBaseline:
    project_id: str
    baseline_id: str
    name: str
    items: tuple[BaselineItem, ...] = ()


@dataclass(frozen=True, slots=True)
class TechnicalDeltaProvenance:
    baseline_item_id: str | None
    decision_id: str | None
    review_event_id: str | None
    accepted_claim_ids: tuple[str, ...]
    authority_decision_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    trace: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TechnicalDelta:
    id: str
    comparison_key: str
    delta_type: DeltaType
    category: str
    title: str
    baseline_value: str | None
    approved_value: str | None
    unit: str | None
    confidence: float | None
    provenance: TechnicalDeltaProvenance
    fingerprint: str
    object_ref: str | None = None
    property_name: str | None = None
    value_kind: ValueKind = ValueKind.TEXT
    baseline_quantity: float | None = None
    approved_quantity: float | None = None
    quantity_delta: float | None = None
    change_direction: ChangeDirection = ChangeDirection.CHANGED


@dataclass(frozen=True, slots=True)
class TechnicalDeltaSet:
    project_id: str
    baseline_id: str
    deltas: tuple[TechnicalDelta, ...] = ()

    @property
    def changed_count(self) -> int:
        return sum(delta.delta_type != DeltaType.UNCHANGED for delta in self.deltas)
