from decimal import Decimal

from crow_pressure_test import ClaimOrigin, TightnessClass, load_knowledge
from crow_pressure_test.workflow import (
    PressureTestStatus,
    RequirementProvenance,
    evaluate_pressure_test,
    evaluation_to_payload,
)


def test_pressure_test_passes_when_measured_flow_is_within_limit() -> None:
    result = evaluate_pressure_test(
        project_id="p1",
        tightness_class=TightnessClass.C,
        pressure_pa=400,
        duct_area_m2=Decimal("10"),
        measured_leakage_lps=Decimal("1"),
        provenance=(
            RequirementProvenance(
                field="tightness_class",
                value="C",
                origin=ClaimOrigin.STATED,
                source_ref="VVS-beskrivning s. 12",
                confirmed=True,
            ),
        ),
        knowledge=load_knowledge(),
    )
    assert result.status is PressureTestStatus.PASS
    assert result.ready_for_protocol is True
    payload = evaluation_to_payload(result)
    assert isinstance(payload["allowed_leakage_lps"], str)
    assert payload["measured_leakage_lps"] == "1"


def test_unconfirmed_inference_blocks_protocol_readiness() -> None:
    result = evaluate_pressure_test(
        project_id="p1",
        tightness_class=TightnessClass.C,
        pressure_pa=400,
        duct_area_m2=Decimal("10"),
        measured_leakage_lps=Decimal("1"),
        provenance=(
            RequirementProvenance(
                field="pre_pour_test",
                value="provning före ingjutning",
                origin=ClaimOrigin.INFERRED,
                confirmed=False,
            ),
        ),
        knowledge=load_knowledge(),
    )
    assert result.status is PressureTestStatus.PASS
    assert result.ready_for_protocol is False
    assert evaluation_to_payload(result)["provenance"][0]["requires_confirmation"] is True


def test_pressure_test_fails_above_allowed_leakage() -> None:
    knowledge = load_knowledge()
    allowed = knowledge.allowed_leakage_flow(TightnessClass.A, 400, Decimal("1"))
    result = evaluate_pressure_test(
        project_id="p1",
        tightness_class=TightnessClass.A,
        pressure_pa=400,
        duct_area_m2=Decimal("1"),
        measured_leakage_lps=allowed + Decimal("0.000001"),
        provenance=(),
        knowledge=knowledge,
    )
    assert result.status is PressureTestStatus.FAIL
