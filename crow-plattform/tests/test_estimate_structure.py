from crow_estimate_line import Estimate, EstimateLine, EstimateLineProvenance, EstimateLineStatus
from crow_estimate_structure import (
    EstimateGroupingProfile,
    EstimateGroupingRule,
    structure_estimate,
)


def line(identifier: str, cost_type: str, amount: float, document: str) -> EstimateLine:
    provenance = EstimateLineProvenance(
        commercial_impact_id=f"commercial:{identifier}",
        scope_impact_id=f"scope:{identifier}",
        technical_delta_id=f"delta:{identifier}",
        decision_id=None,
        review_event_id=None,
        accepted_claim_ids=(),
        authority_decision_ids=(),
        document_ids=(document,),
        scope_rule_id=None,
        price_book_id="book",
        unit_rate_id=None,
        adjustment_profile_id="profile",
        commercial_review_event_id="review:1",
        adjustment_ids=(),
        trace=(),
    )
    return EstimateLine(
        id=f"line:{identifier}",
        line_number=1,
        status=EstimateLineStatus.READY,
        description=identifier,
        cost_type=cost_type,
        quantity=1.0,
        unit="ST",
        unit_rate=amount,
        net_amount=amount,
        adjustment_amount=0.0,
        total_amount=amount,
        currency="SEK",
        provenance=provenance,
        fingerprint=f"fp:{identifier}",
    )


def test_deterministic_hierarchy_and_totals() -> None:
    estimate = Estimate(
        project_id="p",
        baseline_id="b",
        estimate_id="e",
        currency="SEK",
        price_book_id="book",
        adjustment_profile_id="profile",
        commercial_review_event_id="review:1",
        lines=(
            line("material", "material", 200.0, "doc:2"),
            line("labour", "labour", 100.0, "doc:1"),
        ),
    )
    profile = EstimateGroupingProfile(
        id="grouping",
        rules=(
            EstimateGroupingRule(
                "labour",
                "10",
                "Produktion",
                "10",
                "Arbete",
                ("labour",),
                priority=10,
            ),
            EstimateGroupingRule(
                "material",
                "10",
                "Produktion",
                "20",
                "Material",
                ("material",),
                priority=20,
            ),
        ),
    )
    first = structure_estimate(estimate, profile, "structure:1")
    second = structure_estimate(estimate, profile, "structure:1")
    assert first == second
    assert len(first.sections) == 1
    assert len(first.sections[0].groups) == 2
    assert first.sections[0].groups[0].lines[0].position == "1.1.1"
    assert first.grand_total == 300.0
    assert first.sections[0].document_ids == ("doc:1", "doc:2")


def test_fallback_group_receives_unmatched_line() -> None:
    estimate = Estimate(
        project_id="p",
        baseline_id="b",
        estimate_id="e",
        currency="SEK",
        price_book_id="book",
        adjustment_profile_id="profile",
        commercial_review_event_id="review:1",
        lines=(line("risk", "risk", 50.0, "doc:1"),),
    )
    result = structure_estimate(estimate, EstimateGroupingProfile("empty", ()), "s")
    assert result.sections[0].code == "99"
    assert result.sections[0].groups[0].title == "Ej klassificerat"
