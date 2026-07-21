from __future__ import annotations

import hashlib
from typing import Any

from crow_accepted_claims import AcceptedClaim, AcceptedClaimSet

from .models import (
    ConditionEvaluation,
    ConditionOperator,
    DecisionEvaluationResult,
    RuleEvaluation,
    RuleEvaluationStatus,
    RuleSet,
    TechnicalDecisionCandidate,
    TechnicalDecisionProvenance,
    TechnicalDecisionRule,
)
from .multi_claim import evaluate_multi_claim_rules, merge_multi_claim_results
from .operators import evaluate_operator


def _claim_field(claim: AcceptedClaim, field: str) -> Any:
    fields: dict[str, Any] = {
        "id": claim.id,
        "semantic_key": claim.semantic_key,
        "subject": claim.subject,
        "predicate": claim.predicate,
        "value": claim.value,
        "unit": claim.unit,
        "confidence": claim.confidence,
        "acceptance_basis": claim.acceptance_basis.value,
        "framework_id": claim.provenance.framework_id,
        "applied_rule": claim.provenance.applied_rule,
    }
    if field not in fields:
        raise ValueError(f"Unsupported claim field: {field}")
    return fields[field]


def _evaluate_rule(
    rule: TechnicalDecisionRule,
    claim: AcceptedClaim,
) -> RuleEvaluation:
    evaluations: list[ConditionEvaluation] = []
    try:
        for condition in rule.conditions:
            actual = _claim_field(claim, condition.field)
            matched = evaluate_operator(
                actual,
                condition.operator,
                condition.expected,
                condition.case_sensitive,
            )
            evaluations.append(
                ConditionEvaluation(
                    field=condition.field,
                    operator=condition.operator,
                    expected=condition.expected,
                    actual=actual,
                    matched=matched,
                    explanation=(
                        f"{condition.field} {condition.operator.value} "
                        f"{condition.expected!r}: {matched}"
                    ),
                )
            )
    except (TypeError, ValueError) as error:
        evaluations.append(
            ConditionEvaluation(
                field="evaluation",
                operator=(
                    rule.conditions[0].operator if rule.conditions else ConditionOperator.EQUALS
                ),
                expected=None,
                actual=None,
                matched=False,
                explanation=str(error),
            )
        )
        return RuleEvaluation(
            rule_id=rule.id,
            claim_id=claim.id,
            status=RuleEvaluationStatus.INVALID_INPUT,
            conditions=tuple(evaluations),
        )

    status = (
        RuleEvaluationStatus.MATCHED
        if evaluations and all(item.matched for item in evaluations)
        else RuleEvaluationStatus.NOT_MATCHED
    )
    return RuleEvaluation(
        rule_id=rule.id,
        claim_id=claim.id,
        status=status,
        conditions=tuple(evaluations),
    )


def _numeric_or_none(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def _fingerprint(rule: TechnicalDecisionRule, claim: AcceptedClaim) -> str:
    material = "|".join(
        (
            rule.id,
            rule.version,
            claim.fingerprint,
            rule.output.category,
            rule.output.severity.value,
            rule.output.conclusion,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _candidate(
    rule: TechnicalDecisionRule,
    rule_set: RuleSet,
    claim: AcceptedClaim,
    evaluation: RuleEvaluation,
) -> TechnicalDecisionCandidate:
    fingerprint = _fingerprint(rule, claim)
    trace = (
        f"Accepted claim evaluated: {claim.id}",
        f"Rule matched: {rule.id}",
        *(item.explanation for item in evaluation.conditions),
        f"Decision candidate emitted: {rule.output.title}",
    )
    return TechnicalDecisionCandidate(
        id=f"technical-decision:{fingerprint}",
        category=rule.output.category,
        severity=rule.output.severity,
        title=rule.output.title,
        conclusion=rule.output.conclusion,
        recommended_action=rule.output.recommended_action,
        confidence=claim.confidence,
        priority=rule.priority,
        status="proposed",
        provenance=TechnicalDecisionProvenance(
            accepted_claim_ids=(claim.id,),
            authority_decision_ids=(claim.provenance.authority_decision_id,),
            cluster_ids=(claim.provenance.cluster_id,),
            document_ids=claim.provenance.document_ids,
            rule_id=rule.id,
            rule_set_id=rule_set.id,
            rule_version=rule.version,
            trace=trace,
        ),
        fingerprint=fingerprint,
        object_ref=claim.subject,
        property_name=claim.predicate,
        value=claim.value,
        unit=claim.unit,
        quantity=_numeric_or_none(claim.value),
    )


def evaluate_claims(
    claims: AcceptedClaimSet,
    rule_set: RuleSet,
) -> DecisionEvaluationResult:
    evaluations: list[RuleEvaluation] = []
    candidates: list[TechnicalDecisionCandidate] = []

    rules = sorted(
        (rule for rule in rule_set.rules if rule.enabled),
        key=lambda item: (-item.priority, item.id),
    )
    accepted_claims = sorted(claims.claims, key=lambda item: item.id)

    for rule in rules:
        for claim in accepted_claims:
            evaluation = _evaluate_rule(rule, claim)
            evaluations.append(evaluation)
            if evaluation.status == RuleEvaluationStatus.MATCHED:
                candidates.append(_candidate(rule, rule_set, claim, evaluation))

    unique = {item.fingerprint: item for item in candidates}
    ordered_candidates = tuple(sorted(unique.values(), key=lambda item: (-item.priority, item.id)))
    base = DecisionEvaluationResult(
        project_id=claims.project_id,
        rule_set_id=rule_set.id,
        candidates=ordered_candidates,
        evaluations=tuple(evaluations),
    )
    multi_candidates, multi_evaluations = evaluate_multi_claim_rules(claims, rule_set)
    return merge_multi_claim_results(base, multi_candidates, multi_evaluations)
