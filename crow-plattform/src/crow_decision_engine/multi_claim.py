from __future__ import annotations

import ast
import hashlib
import itertools
import re

from crow_accepted_claims import AcceptedClaim, AcceptedClaimSet

from .models import (
    ClaimSelector,
    DecisionEvaluationResult,
    MultiClaimEvaluation,
    MultiClaimRule,
    RuleEvaluationStatus,
    RuleSet,
    TechnicalDecisionCandidate,
    TechnicalDecisionProvenance,
)
from .operators import evaluate_operator


def evaluate_expression(expression: str, values: dict[str, float]) -> float:
    node = ast.parse(expression, mode="eval")

    def visit(item: ast.AST) -> float:
        if isinstance(item, ast.Expression):
            return visit(item.body)
        if isinstance(item, ast.Constant) and isinstance(item.value, (int, float)):
            return float(item.value)
        if isinstance(item, ast.Name):
            if item.id not in values:
                raise ValueError(f"Unknown expression alias: {item.id}")
            return values[item.id]
        if isinstance(item, ast.BinOp):
            left = visit(item.left)
            right = visit(item.right)
            if isinstance(item.op, ast.Add):
                return left + right
            if isinstance(item.op, ast.Sub):
                return left - right
            if isinstance(item.op, ast.Mult):
                return left * right
            if isinstance(item.op, ast.Div):
                return left / right
            if isinstance(item.op, ast.Pow):
                return float(left**right)
        if isinstance(item, ast.UnaryOp):
            operand = visit(item.operand)
            if isinstance(item.op, ast.UAdd):
                return operand
            if isinstance(item.op, ast.USub):
                return -operand
        raise ValueError(f"Unsupported expression element: {type(item).__name__}")

    return visit(node)


def _matches(claim: AcceptedClaim, selector: ClaimSelector) -> bool:
    if claim.confidence < selector.minimum_confidence:
        return False
    if selector.subject is not None and claim.subject.casefold() != selector.subject.casefold():
        return False
    if selector.subject_regex is not None:
        if re.search(selector.subject_regex, claim.subject, re.IGNORECASE) is None:
            return False
    if selector.predicate is not None:
        if claim.predicate.casefold() != selector.predicate.casefold():
            return False
    if selector.unit is not None:
        if claim.unit is None or claim.unit.casefold() != selector.unit.casefold():
            return False
    if selector.semantic_key_contains is not None:
        if selector.semantic_key_contains.casefold() not in claim.semantic_key.casefold():
            return False
    return True


def _candidate_fingerprint(
    rule: MultiClaimRule,
    claims: tuple[AcceptedClaim, ...],
    calculated: float,
) -> str:
    material = "|".join(
        (
            rule.id,
            rule.version,
            *(claim.fingerprint for claim in claims),
            f"{calculated:.12g}",
            rule.output.conclusion,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _make_candidate(
    rule: MultiClaimRule,
    rule_set: RuleSet,
    claims: tuple[AcceptedClaim, ...],
    calculated: float,
    evaluation: MultiClaimEvaluation,
) -> TechnicalDecisionCandidate:
    fingerprint = _candidate_fingerprint(rule, claims, calculated)
    return TechnicalDecisionCandidate(
        id=f"technical-decision:{fingerprint}",
        category=rule.output.category,
        severity=rule.output.severity,
        title=rule.output.title,
        conclusion=rule.output.conclusion,
        recommended_action=rule.output.recommended_action,
        confidence=min(claim.confidence for claim in claims),
        priority=rule.priority,
        status="proposed",
        provenance=TechnicalDecisionProvenance(
            accepted_claim_ids=tuple(claim.id for claim in claims),
            authority_decision_ids=tuple(
                claim.provenance.authority_decision_id for claim in claims
            ),
            cluster_ids=tuple(claim.provenance.cluster_id for claim in claims),
            document_ids=tuple(
                dict.fromkeys(
                    document_id for claim in claims for document_id in claim.provenance.document_ids
                )
            ),
            rule_id=rule.id,
            rule_set_id=rule_set.id,
            rule_version=rule.version,
            trace=(
                *(
                    f"{alias} bound to {claim.id}"
                    for alias, claim in zip(
                        (selector.alias for selector in rule.selectors),
                        claims,
                        strict=True,
                    )
                ),
                f"Expression {rule.expression} = {calculated:.12g}",
                evaluation.explanation,
                f"Decision candidate emitted: {rule.output.title}",
            ),
        ),
        fingerprint=fingerprint,
        object_ref=" + ".join(claim.subject for claim in claims),
        property_name=rule.id,
        value=f"{calculated:.12g}",
        unit=None,
        quantity=calculated,
    )


def evaluate_multi_claim_rules(
    claims: AcceptedClaimSet,
    rule_set: RuleSet,
) -> tuple[tuple[TechnicalDecisionCandidate, ...], tuple[MultiClaimEvaluation, ...]]:
    candidates: list[TechnicalDecisionCandidate] = []
    evaluations: list[MultiClaimEvaluation] = []

    for rule in sorted(
        (item for item in rule_set.multi_rules if item.enabled),
        key=lambda item: (-item.priority, item.id),
    ):
        selections = [
            tuple(claim for claim in claims.claims if _matches(claim, selector))
            for selector in rule.selectors
        ]
        if any(not selection for selection in selections):
            evaluations.append(
                MultiClaimEvaluation(
                    rule_id=rule.id,
                    claim_ids=(),
                    status=RuleEvaluationStatus.NOT_MATCHED,
                    bindings=(),
                    expression=rule.expression,
                    calculated_value=None,
                    comparison=rule.comparison,
                    expected=rule.expected,
                    explanation="One or more selectors had no matching accepted claim.",
                )
            )
            continue

        for combination in itertools.product(*selections):
            if len({claim.id for claim in combination}) != len(combination):
                continue
            bindings = tuple(
                (selector.alias, claim.id)
                for selector, claim in zip(rule.selectors, combination, strict=True)
            )
            try:
                values = {
                    selector.alias: float(claim.value.replace(",", "."))
                    for selector, claim in zip(rule.selectors, combination, strict=True)
                }
                calculated = evaluate_expression(rule.expression, values)
                matched = evaluate_operator(
                    calculated,
                    rule.comparison,
                    rule.expected,
                )
                status = (
                    RuleEvaluationStatus.MATCHED if matched else RuleEvaluationStatus.NOT_MATCHED
                )
                explanation = (
                    f"Calculated {calculated:.12g} "
                    f"{rule.comparison.value} {rule.expected}: {matched}"
                )
            except (TypeError, ValueError, ZeroDivisionError) as error:
                calculated = None
                status = RuleEvaluationStatus.INVALID_INPUT
                explanation = str(error)

            evaluation = MultiClaimEvaluation(
                rule_id=rule.id,
                claim_ids=tuple(claim.id for claim in combination),
                status=status,
                bindings=bindings,
                expression=rule.expression,
                calculated_value=calculated,
                comparison=rule.comparison,
                expected=rule.expected,
                explanation=explanation,
            )
            evaluations.append(evaluation)
            if status == RuleEvaluationStatus.MATCHED and calculated is not None:
                candidates.append(
                    _make_candidate(rule, rule_set, combination, calculated, evaluation)
                )

    unique = {candidate.fingerprint: candidate for candidate in candidates}
    return (
        tuple(sorted(unique.values(), key=lambda item: (-item.priority, item.id))),
        tuple(evaluations),
    )


def merge_multi_claim_results(
    base: DecisionEvaluationResult,
    candidates: tuple[TechnicalDecisionCandidate, ...],
    evaluations: tuple[MultiClaimEvaluation, ...],
) -> DecisionEvaluationResult:
    all_candidates = {item.fingerprint: item for item in (*base.candidates, *candidates)}
    return DecisionEvaluationResult(
        project_id=base.project_id,
        rule_set_id=base.rule_set_id,
        candidates=tuple(
            sorted(all_candidates.values(), key=lambda item: (-item.priority, item.id))
        ),
        evaluations=base.evaluations,
        multi_evaluations=evaluations,
    )
