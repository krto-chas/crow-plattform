from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InferenceRule:
    id: str
    premise_relation: str
    conclusion_relation: str
    transitive: bool = True
    max_depth: int = 12
    confidence_factor: float = 0.98
    description: str = ""
    enabled: bool = True
    chainable: bool = True


@dataclass(frozen=True)
class ExplanationStep:
    relation_id: str
    source_id: str
    relation_type: str
    target_id: str
    confidence: float
    derived: bool = False
    rule_id: str | None = None
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DerivedRelation:
    id: str
    source_id: str
    relation_type: str
    target_id: str
    confidence: float
    rule_id: str
    explanation: tuple[ExplanationStep, ...]
    evidence_ids: tuple[str, ...] = ()
    iteration: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InferenceConflict:
    id: str
    subject_id: str
    predicate: str
    values: tuple[Any, ...]
    property_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()
    severity: str = "warning"
    message: str = "Motstridiga värden kräver verifiering"
    resolution_status: str = "unresolved"
