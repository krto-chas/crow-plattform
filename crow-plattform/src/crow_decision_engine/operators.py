from __future__ import annotations

import re
from typing import Any

from .models import ConditionOperator


def _number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a numeric decision value")
    return float(str(value).replace(",", "."))


def evaluate_operator(
    actual: Any,
    operator: ConditionOperator,
    expected: Any,
    case_sensitive: bool = False,
) -> bool:
    if operator == ConditionOperator.EXISTS:
        expected_exists = True if expected is None else bool(expected)
        return (actual is not None and str(actual) != "") is expected_exists

    if actual is None:
        return False

    if operator in {
        ConditionOperator.GREATER_THAN,
        ConditionOperator.GREATER_THAN_OR_EQUAL,
        ConditionOperator.LESS_THAN,
        ConditionOperator.LESS_THAN_OR_EQUAL,
    }:
        left = _number(actual)
        right = _number(expected)
        if operator == ConditionOperator.GREATER_THAN:
            return left > right
        if operator == ConditionOperator.GREATER_THAN_OR_EQUAL:
            return left >= right
        if operator == ConditionOperator.LESS_THAN:
            return left < right
        return left <= right

    left_text = str(actual)
    right_text = "" if expected is None else str(expected)
    if not case_sensitive:
        left_text = left_text.casefold()
        right_text = right_text.casefold()

    if operator == ConditionOperator.EQUALS:
        return left_text == right_text
    if operator == ConditionOperator.NOT_EQUALS:
        return left_text != right_text
    if operator == ConditionOperator.CONTAINS:
        return right_text in left_text
    if operator == ConditionOperator.REGEX:
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(str(expected), str(actual), flags) is not None
    raise ValueError(f"Unsupported operator: {operator.value}")
