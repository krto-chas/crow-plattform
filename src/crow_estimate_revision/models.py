from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EstimateChangeType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class EstimateFieldChange:
    field: str
    previous: str | float | None
    current: str | float | None


@dataclass(frozen=True, slots=True)
class EstimateLineChange:
    id: str
    change_type: EstimateChangeType
    estimate_line_id: str
    previous_position: str | None
    current_position: str | None
    previous_fingerprint: str | None
    current_fingerprint: str | None
    field_changes: tuple[EstimateFieldChange, ...]
    explanation: str
    amount_delta: float
    fingerprint: str


@dataclass(frozen=True, slots=True)
class EstimateRevision:
    id: str
    project_id: str
    baseline_id: str
    previous_estimate_id: str
    current_estimate_id: str
    previous_structure_id: str
    current_structure_id: str
    previous_fingerprint: str
    current_fingerprint: str
    currency: str
    line_changes: tuple[EstimateLineChange, ...]
    previous_total: float
    current_total: float
    total_delta: float
    fingerprint: str

    @property
    def added_count(self) -> int:
        return sum(c.change_type is EstimateChangeType.ADDED for c in self.line_changes)

    @property
    def removed_count(self) -> int:
        return sum(c.change_type is EstimateChangeType.REMOVED for c in self.line_changes)

    @property
    def modified_count(self) -> int:
        return sum(c.change_type is EstimateChangeType.MODIFIED for c in self.line_changes)

    @property
    def unchanged_count(self) -> int:
        return sum(c.change_type is EstimateChangeType.UNCHANGED for c in self.line_changes)
