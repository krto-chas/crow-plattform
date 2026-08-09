from __future__ import annotations

from decimal import Decimal

import pytest

from crow_pressure_test import TightnessClass, load_knowledge


def test_leakage_factors_match_ss_en_1507() -> None:
    knowledge = load_knowledge()
    assert knowledge.leakage_factor(TightnessClass.A) == Decimal("0.027")
    assert knowledge.leakage_factor(TightnessClass.B) == Decimal("0.009")
    assert knowledge.leakage_factor(TightnessClass.C) == Decimal("0.003")
    assert knowledge.leakage_factor(TightnessClass.D) == Decimal("0.001")


def test_adjacent_classes_differ_by_factor_three() -> None:
    knowledge = load_knowledge()
    assert knowledge.leakage_factor(TightnessClass.A) == 3 * knowledge.leakage_factor(
        TightnessClass.B
    )
    assert knowledge.leakage_factor(TightnessClass.B) == 3 * knowledge.leakage_factor(
        TightnessClass.C
    )
    assert knowledge.leakage_factor(TightnessClass.C) == 3 * knowledge.leakage_factor(
        TightnessClass.D
    )


def test_allowed_leakage_flow_class_c_at_400_pa() -> None:
    knowledge = load_knowledge()
    flow = knowledge.allowed_leakage_flow(TightnessClass.C, 400, Decimal("1"))
    assert Decimal("0.147") < flow < Decimal("0.148")


def test_allowed_leakage_flow_uses_absolute_pressure() -> None:
    knowledge = load_knowledge()
    positive = knowledge.allowed_leakage_flow(TightnessClass.C, 400, Decimal("6.5"))
    negative = knowledge.allowed_leakage_flow(TightnessClass.C, -400, Decimal("6.5"))
    assert positive == negative


def test_allowed_leakage_flow_is_deterministic() -> None:
    knowledge = load_knowledge()
    first = knowledge.allowed_leakage_flow(TightnessClass.B, 400, Decimal("12.34"))
    second = knowledge.allowed_leakage_flow(TightnessClass.B, 400, Decimal("12.34"))
    assert first == second
    assert first == first.quantize(Decimal("0.000001"))


def test_allowed_leakage_flow_rejects_invalid_input() -> None:
    knowledge = load_knowledge()
    with pytest.raises(ValueError):
        knowledge.allowed_leakage_flow(TightnessClass.C, 0, Decimal("1"))
    with pytest.raises(ValueError):
        knowledge.allowed_leakage_flow(TightnessClass.C, 400, Decimal("0"))


def test_atc_mapping_and_standards_registry() -> None:
    knowledge = load_knowledge()
    assert knowledge.atc_class(TightnessClass.C) == "ATC 4"
    standard_ids = {standard.standard_id for standard in knowledge.standards()}
    assert {"SS-EN 1507", "SS-EN 12237", "SS-EN 14239", "SS-EN 16798-3"} <= standard_ids
