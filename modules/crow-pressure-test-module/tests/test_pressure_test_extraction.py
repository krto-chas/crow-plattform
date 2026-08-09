from __future__ import annotations

from crow_pressure_test import (
    ClaimOrigin,
    TightnessClass,
    extract_test_scope,
    extract_tightness_requirements,
    find_conflicts,
    load_knowledge,
)

_KRAVTABELL = """Krav på täthet
Rektangulära kanaler skall utföras i täthetsklass C.
Cirkulära kanaler skall utföras i täthetsklass C.
Imkanaler (lgh) skall utföras i täthetsklass C.
"""

_QL_MENING = (
    "Kanalsystem utförs med täthetsklass C för cirkulära kanaler "
    "och täthetsklass B för rektangulära kanaler."
)

_OMFATTNING = """Täthetsprovning av typgodkända kanalsystem skall utföras enligt omfattning:
Schakt: 100 %
Rektangulära kanaler: 10 %
Cirkulära kanaler: 10 %
Ej typgodkända kanalsystem provas till 100 %
"""


def test_extracts_one_requirement_per_table_row() -> None:
    knowledge = load_knowledge()
    requirements = extract_tightness_requirements(_KRAVTABELL, "besk", knowledge)
    by_family = {item.duct_family: item for item in requirements}
    assert set(by_family) == {"rektangular", "cirkular", "imkanal"}
    assert all(item.tightness_class is TightnessClass.C for item in requirements)
    assert all(item.origin is ClaimOrigin.STATED for item in requirements)


def test_compound_sentence_yields_two_distinct_requirements() -> None:
    knowledge = load_knowledge()
    requirements = extract_tightness_requirements(_QL_MENING, "besk-ql", knowledge)
    by_family = {item.duct_family: item.tightness_class for item in requirements}
    assert by_family == {
        "cirkular": TightnessClass.C,
        "rektangular": TightnessClass.B,
    }


def test_locator_preserves_quote_and_line_number() -> None:
    knowledge = load_knowledge()
    requirements = extract_tightness_requirements(_KRAVTABELL, "besk", knowledge)
    rectangular = next(item for item in requirements if item.duct_family == "rektangular")
    assert rectangular.locator.document_id == "besk"
    assert rectangular.locator.line_number == 2
    assert "täthetsklass C" in rectangular.locator.source_text


def test_conflict_detected_between_table_and_ql() -> None:
    knowledge = load_knowledge()
    requirements = extract_tightness_requirements(
        _KRAVTABELL, "besk", knowledge
    ) + extract_tightness_requirements(_QL_MENING, "besk-ql", knowledge)
    conflicts = find_conflicts(requirements)
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.duct_family == "rektangular"
    assert conflict.classes == (TightnessClass.B, TightnessClass.C)
    assert conflict.strictest_class is TightnessClass.C
    documents = {item.locator.document_id for item in conflict.requirements}
    assert documents == {"besk", "besk-ql"}


def test_no_conflict_when_classes_agree() -> None:
    knowledge = load_knowledge()
    requirements = extract_tightness_requirements(_KRAVTABELL, "besk", knowledge)
    assert find_conflicts(requirements) == ()


def test_scope_extraction_matches_berghallen_pattern() -> None:
    knowledge = load_knowledge()
    scopes = extract_test_scope(_OMFATTNING, "besk", knowledge)
    by_target = {item.target: item.percentage for item in scopes}
    assert by_target == {
        "schakt": 100,
        "rektangular": 10,
        "cirkular": 10,
        "platsbyggd": 100,
    }
    assert all(item.origin is ClaimOrigin.STATED for item in scopes)


def test_scope_ignores_percentages_without_duct_context() -> None:
    knowledge = load_knowledge()
    scopes = extract_test_scope("Entreprenören lämnar 10 % rabatt.", "af", knowledge)
    assert scopes == ()
