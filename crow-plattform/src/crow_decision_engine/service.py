from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_accepted_claims import load_accepted_claims

from .engine import evaluate_claims
from .models import (
    ClaimSelector,
    ConditionEvaluation,
    ConditionOperator,
    DecisionEvaluationResult,
    DecisionOutputTemplate,
    DecisionSeverity,
    MultiClaimEvaluation,
    MultiClaimRule,
    RuleCondition,
    RuleEvaluation,
    RuleEvaluationStatus,
    RuleSet,
    TechnicalDecisionCandidate,
    TechnicalDecisionProvenance,
    TechnicalDecisionRule,
)


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def save_rule_set(rule_set: RuleSet, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(rule_set), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_rule_set(path: Path) -> RuleSet:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    rules = tuple(
        TechnicalDecisionRule(
            id=item["id"],
            name=item["name"],
            description=item.get("description", ""),
            priority=int(item.get("priority", 0)),
            enabled=bool(item.get("enabled", True)),
            conditions=tuple(
                RuleCondition(
                    field=condition["field"],
                    operator=ConditionOperator(condition["operator"]),
                    expected=condition.get("expected"),
                    case_sensitive=bool(condition.get("case_sensitive", False)),
                )
                for condition in item.get("conditions", [])
            ),
            output=DecisionOutputTemplate(
                category=item["output"]["category"],
                severity=DecisionSeverity(item["output"]["severity"]),
                title=item["output"]["title"],
                conclusion=item["output"]["conclusion"],
                recommended_action=item["output"].get("recommended_action"),
            ),
            source=item.get("source", "unspecified"),
            version=item.get("version", "1.0.0"),
        )
        for item in raw.get("rules", [])
    )
    multi_rules = tuple(
        MultiClaimRule(
            id=item["id"],
            name=item["name"],
            description=item.get("description", ""),
            priority=int(item.get("priority", 0)),
            enabled=bool(item.get("enabled", True)),
            selectors=tuple(
                ClaimSelector(
                    alias=selector["alias"],
                    subject=selector.get("subject"),
                    subject_regex=selector.get("subject_regex"),
                    predicate=selector.get("predicate"),
                    unit=selector.get("unit"),
                    semantic_key_contains=selector.get("semantic_key_contains"),
                    minimum_confidence=float(selector.get("minimum_confidence", 0.0)),
                )
                for selector in item.get("selectors", [])
            ),
            expression=item["expression"],
            comparison=ConditionOperator(item["comparison"]),
            expected=float(item["expected"]),
            output=DecisionOutputTemplate(
                category=item["output"]["category"],
                severity=DecisionSeverity(item["output"]["severity"]),
                title=item["output"]["title"],
                conclusion=item["output"]["conclusion"],
                recommended_action=item["output"].get("recommended_action"),
            ),
            source=item.get("source", "unspecified"),
            version=item.get("version", "1.0.0"),
        )
        for item in raw.get("multi_rules", [])
    )
    return RuleSet(
        id=raw["id"],
        name=raw["name"],
        version=raw.get("version", "1.0.0"),
        rules=rules,
        multi_rules=multi_rules,
    )


def write_rule_set_template(path: Path) -> None:
    payload = {
        "id": "crow.rules.technical.example",
        "name": "Example technical decision rules",
        "version": "1.0.0",
        "rules": [
            {
                "id": "ventilation.airflow.high",
                "name": "High airflow",
                "description": "Flags accepted airflow values above a configured threshold.",
                "priority": 100,
                "enabled": True,
                "source": "Project technical rule",
                "version": "1.0.0",
                "conditions": [
                    {"field": "predicate", "operator": "equals", "expected": "has_value"},
                    {"field": "unit", "operator": "equals", "expected": "L/S"},
                    {"field": "value", "operator": "greater_than", "expected": 350},
                ],
                "output": {
                    "category": "ventilation",
                    "severity": "medium",
                    "title": "High accepted airflow",
                    "conclusion": "The accepted airflow exceeds the configured threshold.",
                    "recommended_action": "Verify sizing and downstream capacity.",
                },
            }
        ],
        "multi_rules": [
            {
                "id": "ventilation.velocity.limit",
                "name": "Calculated duct velocity",
                "description": "Combines accepted airflow and duct area.",
                "priority": 120,
                "enabled": True,
                "source": "Project technical rule",
                "version": "1.0.0",
                "selectors": [
                    {
                        "alias": "airflow",
                        "subject_regex": "airflow|luftflöde",
                        "unit": "L/S",
                        "minimum_confidence": 0.7,
                    },
                    {
                        "alias": "area",
                        "subject_regex": "duct area|kanalarea",
                        "unit": "M2",
                        "minimum_confidence": 0.7,
                    },
                ],
                "expression": "(airflow / 1000) / area",
                "comparison": "greater_than",
                "expected": 5.0,
                "output": {
                    "category": "ventilation",
                    "severity": "high",
                    "title": "Calculated air velocity exceeds limit",
                    "conclusion": "Accepted airflow and duct area imply excessive velocity.",
                    "recommended_action": "Increase duct area or revise airflow.",
                },
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_decision_result(result: DecisionEvaluationResult, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(result), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_decision_result(path: Path) -> DecisionEvaluationResult:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    candidates = tuple(
        TechnicalDecisionCandidate(
            id=item["id"],
            category=item["category"],
            severity=DecisionSeverity(item["severity"]),
            title=item["title"],
            conclusion=item["conclusion"],
            recommended_action=item.get("recommended_action"),
            confidence=float(item["confidence"]),
            priority=int(item["priority"]),
            status=item["status"],
            provenance=TechnicalDecisionProvenance(
                accepted_claim_ids=tuple(item["provenance"]["accepted_claim_ids"]),
                authority_decision_ids=tuple(item["provenance"]["authority_decision_ids"]),
                cluster_ids=tuple(item["provenance"]["cluster_ids"]),
                document_ids=tuple(item["provenance"]["document_ids"]),
                rule_id=item["provenance"]["rule_id"],
                rule_set_id=item["provenance"]["rule_set_id"],
                rule_version=item["provenance"]["rule_version"],
                trace=tuple(item["provenance"]["trace"]),
            ),
            fingerprint=item["fingerprint"],
            object_ref=item.get("object_ref"),
            property_name=item.get("property_name"),
            value=item.get("value"),
            unit=item.get("unit"),
            quantity=(float(item["quantity"]) if item.get("quantity") is not None else None),
        )
        for item in raw.get("candidates", [])
    )
    evaluations = tuple(
        RuleEvaluation(
            rule_id=item["rule_id"],
            claim_id=item["claim_id"],
            status=RuleEvaluationStatus(item["status"]),
            conditions=tuple(
                ConditionEvaluation(
                    field=condition["field"],
                    operator=ConditionOperator(condition["operator"]),
                    expected=condition.get("expected"),
                    actual=condition.get("actual"),
                    matched=bool(condition["matched"]),
                    explanation=condition["explanation"],
                )
                for condition in item.get("conditions", [])
            ),
        )
        for item in raw.get("evaluations", [])
    )
    multi_evaluations = tuple(
        MultiClaimEvaluation(
            rule_id=item["rule_id"],
            claim_ids=tuple(item["claim_ids"]),
            status=RuleEvaluationStatus(item["status"]),
            bindings=tuple((binding[0], binding[1]) for binding in item["bindings"]),
            expression=item["expression"],
            calculated_value=(
                float(item["calculated_value"])
                if item.get("calculated_value") is not None
                else None
            ),
            comparison=ConditionOperator(item["comparison"]),
            expected=float(item["expected"]),
            explanation=item["explanation"],
        )
        for item in raw.get("multi_evaluations", [])
    )
    return DecisionEvaluationResult(
        project_id=raw["project_id"],
        rule_set_id=raw["rule_set_id"],
        candidates=candidates,
        evaluations=evaluations,
        multi_evaluations=multi_evaluations,
    )


class DecisionSummary(TypedDict):
    project_id: str
    rule_set_id: str
    evaluated: int
    candidates: int
    by_severity: dict[str, int]
    by_category: dict[str, int]


def summarize_decisions(result: DecisionEvaluationResult) -> DecisionSummary:
    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for candidate in result.candidates:
        severity = candidate.severity.value
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_category[candidate.category] = by_category.get(candidate.category, 0) + 1
    return {
        "project_id": result.project_id,
        "rule_set_id": result.rule_set_id,
        "evaluated": result.evaluated_count,
        "candidates": result.matched_count,
        "by_severity": dict(sorted(by_severity.items())),
        "by_category": dict(sorted(by_category.items())),
    }


def evaluate_project(
    project_file: Path,
    rule_set_file: Path,
    accepted_claims_file: Path | None = None,
) -> tuple[DecisionEvaluationResult, Path]:
    claims_path = accepted_claims_file or project_file.with_name("crow-accepted-claims.json")
    claims = load_accepted_claims(claims_path)
    rule_set = load_rule_set(rule_set_file)
    result = evaluate_claims(claims, rule_set)
    output = project_file.with_name("crow-technical-decisions.json")
    save_decision_result(result, output)
    return result, output
