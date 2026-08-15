import pytest

from crow_decision_engine import ConditionOperator, evaluate_operator


def test_text_operators_are_case_insensitive_by_default() -> None:
    assert evaluate_operator("L/S", ConditionOperator.EQUALS, "l/s")
    assert evaluate_operator("Technical Description", ConditionOperator.CONTAINS, "description")


def test_numeric_operators_accept_decimal_strings() -> None:
    assert evaluate_operator("400", ConditionOperator.GREATER_THAN, 350)
    assert evaluate_operator("3,5", ConditionOperator.LESS_THAN_OR_EQUAL, 3.5)


def test_exists_operator() -> None:
    assert evaluate_operator("value", ConditionOperator.EXISTS, True)
    assert evaluate_operator(None, ConditionOperator.EXISTS, False)


def test_invalid_numeric_value_raises() -> None:
    with pytest.raises(ValueError):
        evaluate_operator("not-number", ConditionOperator.GREATER_THAN, 2)
