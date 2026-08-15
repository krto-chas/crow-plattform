from dataclasses import replace

import pytest

from crow_estimate_revision import EstimateChangeType, compare_estimates
from crow_estimate_structure import (
    BillOfQuantityLine,
    EstimateGroup,
    EstimateSection,
    StructuredEstimate,
)


def boq(line_id: str, position: str, total: float, fingerprint: str) -> BillOfQuantityLine:
    return BillOfQuantityLine(
        id=f"boq:{line_id}:{fingerprint}",
        position=position,
        estimate_line_id=line_id,
        description=line_id,
        quantity=1.0,
        unit="ST",
        unit_rate=total,
        net_amount=total,
        adjustment_amount=0.0,
        total_amount=total,
        currency="SEK",
        fingerprint=fingerprint,
    )


def structured(
    estimate_id: str,
    structure_id: str,
    lines: tuple[BillOfQuantityLine, ...],
) -> StructuredEstimate:
    net = sum(line.net_amount for line in lines)
    adjustment = sum(line.adjustment_amount for line in lines)
    total = sum(line.total_amount for line in lines)
    group = EstimateGroup(
        id=f"group:{structure_id}",
        code="10",
        title="Produktion",
        position="1.1",
        lines=lines,
        estimate_line_ids=tuple(line.estimate_line_id for line in lines),
        document_ids=("doc:1",),
        net_total=net,
        adjustment_total=adjustment,
        grand_total=total,
        fingerprint=f"group-fp:{structure_id}",
    )
    section = EstimateSection(
        id=f"section:{structure_id}",
        code="10",
        title="Produktion",
        position="1",
        groups=(group,),
        estimate_line_ids=group.estimate_line_ids,
        document_ids=("doc:1",),
        net_total=net,
        adjustment_total=adjustment,
        grand_total=total,
        fingerprint=f"section-fp:{structure_id}",
    )
    return StructuredEstimate(
        project_id="project",
        baseline_id="baseline",
        estimate_id=estimate_id,
        structure_id=structure_id,
        grouping_profile_id="profile",
        currency="SEK",
        sections=(section,),
        source_line_ids=tuple(sorted(group.estimate_line_ids)),
        fingerprint=f"structure-fp:{structure_id}",
    )


def test_revision_detects_added_removed_and_modified() -> None:
    previous = structured(
        "estimate-1",
        "structure-1",
        (
            boq("line:removed", "1.1.1", 100.0, "old-removed"),
            boq("line:modified", "1.1.2", 200.0, "old-modified"),
        ),
    )
    current = structured(
        "estimate-2",
        "structure-2",
        (
            boq("line:modified", "1.1.1", 250.0, "new-modified"),
            boq("line:added", "1.1.2", 75.0, "new-added"),
        ),
    )

    revision = compare_estimates(previous, current, "REV-002")
    kinds = {change.estimate_line_id: change.change_type for change in revision.line_changes}

    assert kinds == {
        "line:added": EstimateChangeType.ADDED,
        "line:modified": EstimateChangeType.MODIFIED,
        "line:removed": EstimateChangeType.REMOVED,
    }
    assert revision.total_delta == 25.0
    assert sum(change.amount_delta for change in revision.line_changes) == 25.0
    modified = next(
        change for change in revision.line_changes if change.estimate_line_id == "line:modified"
    )
    assert {change.field for change in modified.field_changes} == {
        "position",
        "unit_rate",
        "net_amount",
        "total_amount",
    }


def test_revision_is_deterministic_and_can_include_unchanged() -> None:
    line = boq("line:stable", "1.1.1", 100.0, "stable")
    previous = structured("estimate-1", "structure-1", (line,))
    current = structured("estimate-2", "structure-2", (line,))

    first = compare_estimates(previous, current, "REV-002", include_unchanged=True)
    second = compare_estimates(previous, current, "REV-002", include_unchanged=True)

    assert first == second
    assert first.unchanged_count == 1
    assert first.total_delta == 0.0


def test_revision_rejects_different_projects() -> None:
    previous = structured(
        "estimate-1",
        "structure-1",
        (boq("line:1", "1.1.1", 100.0, "one"),),
    )
    current = replace(
        structured(
            "estimate-2",
            "structure-2",
            (boq("line:1", "1.1.1", 100.0, "one"),),
        ),
        project_id="another-project",
    )

    with pytest.raises(ValueError, match="Project IDs"):
        compare_estimates(previous, current, "REV-002")
