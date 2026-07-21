from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EstimateGroupingRule:
    id: str
    section_code: str
    section_title: str
    group_code: str
    group_title: str
    cost_types: tuple[str, ...] = ()
    description_contains: tuple[str, ...] = ()
    priority: int = 100


@dataclass(frozen=True, slots=True)
class EstimateGroupingProfile:
    id: str
    rules: tuple[EstimateGroupingRule, ...]
    fallback_section_code: str = "99"
    fallback_section_title: str = "Övrigt"
    fallback_group_code: str = "99"
    fallback_group_title: str = "Ej klassificerat"


@dataclass(frozen=True, slots=True)
class BillOfQuantityLine:
    id: str
    position: str
    estimate_line_id: str
    description: str
    quantity: float
    unit: str
    unit_rate: float
    net_amount: float
    adjustment_amount: float
    total_amount: float
    currency: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class EstimateGroup:
    id: str
    code: str
    title: str
    position: str
    lines: tuple[BillOfQuantityLine, ...]
    estimate_line_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    net_total: float
    adjustment_total: float
    grand_total: float
    fingerprint: str


@dataclass(frozen=True, slots=True)
class EstimateSection:
    id: str
    code: str
    title: str
    position: str
    groups: tuple[EstimateGroup, ...]
    estimate_line_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    net_total: float
    adjustment_total: float
    grand_total: float
    fingerprint: str


@dataclass(frozen=True, slots=True)
class StructuredEstimate:
    project_id: str
    baseline_id: str
    estimate_id: str
    structure_id: str
    grouping_profile_id: str
    currency: str
    sections: tuple[EstimateSection, ...]
    source_line_ids: tuple[str, ...]
    fingerprint: str

    @property
    def net_total(self) -> float:
        return sum(section.net_total for section in self.sections)

    @property
    def adjustment_total(self) -> float:
        return sum(section.adjustment_total for section in self.sections)

    @property
    def grand_total(self) -> float:
        return sum(section.grand_total for section in self.sections)
