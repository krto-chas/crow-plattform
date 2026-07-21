from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ConditionOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    EXISTS = "exists"
    REGEX = "regex"


class DecisionSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleEvaluationStatus(StrEnum):
    MATCHED = "matched"
    NOT_MATCHED = "not_matched"
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True, slots=True)
class RuleCondition:
    field: str
    operator: ConditionOperator
    expected: str | float | bool | None = None
    case_sensitive: bool = False


@dataclass(frozen=True, slots=True)
class DecisionOutputTemplate:
    category: str
    severity: DecisionSeverity
    title: str
    conclusion: str
    recommended_action: str | None = None


@dataclass(frozen=True, slots=True)
class TechnicalDecisionRule:
    id: str
    name: str
    description: str
    priority: int
    enabled: bool
    conditions: tuple[RuleCondition, ...]
    output: DecisionOutputTemplate
    source: str
    version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class ClaimSelector:
    alias: str
    subject: str | None = None
    subject_regex: str | None = None
    predicate: str | None = None
    unit: str | None = None
    semantic_key_contains: str | None = None
    minimum_confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class MultiClaimRule:
    id: str
    name: str
    description: str
    priority: int
    enabled: bool
    selectors: tuple[ClaimSelector, ...]
    expression: str
    comparison: ConditionOperator
    expected: float
    output: DecisionOutputTemplate
    source: str
    version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class RuleSet:
    id: str
    name: str
    version: str
    rules: tuple[TechnicalDecisionRule, ...]
    multi_rules: tuple[MultiClaimRule, ...] = ()


@dataclass(frozen=True, slots=True)
class ConditionEvaluation:
    field: str
    operator: ConditionOperator
    expected: str | float | bool | None
    actual: str | float | bool | None
    matched: bool
    explanation: str


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    rule_id: str
    claim_id: str
    status: RuleEvaluationStatus
    conditions: tuple[ConditionEvaluation, ...]


@dataclass(frozen=True, slots=True)
class MultiClaimEvaluation:
    rule_id: str
    claim_ids: tuple[str, ...]
    status: RuleEvaluationStatus
    bindings: tuple[tuple[str, str], ...]
    expression: str
    calculated_value: float | None
    comparison: ConditionOperator
    expected: float
    explanation: str


@dataclass(frozen=True, slots=True)
class TechnicalDecisionProvenance:
    accepted_claim_ids: tuple[str, ...]
    authority_decision_ids: tuple[str, ...]
    cluster_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    rule_id: str
    rule_set_id: str
    rule_version: str
    trace: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TechnicalDecisionCandidate:
    id: str
    category: str
    severity: DecisionSeverity
    title: str
    conclusion: str
    recommended_action: str | None
    confidence: float
    priority: int
    status: str
    provenance: TechnicalDecisionProvenance
    fingerprint: str
    object_ref: str | None = None
    property_name: str | None = None
    value: str | None = None
    unit: str | None = None
    quantity: float | None = None


@dataclass(frozen=True, slots=True)
class DecisionEvaluationResult:
    project_id: str
    rule_set_id: str
    candidates: tuple[TechnicalDecisionCandidate, ...] = ()
    evaluations: tuple[RuleEvaluation, ...] = ()
    multi_evaluations: tuple[MultiClaimEvaluation, ...] = ()

    @property
    def matched_count(self) -> int:
        return len(self.candidates)

    @property
    def evaluated_count(self) -> int:
        return len(self.evaluations) + len(self.multi_evaluations)
