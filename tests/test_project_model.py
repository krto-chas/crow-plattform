from decimal import Decimal

import pytest
from crow_example_module import ExamplePlugin

from crow_module_sdk import (
    AuthorityPolicy,
    AuthorityRule,
    Claim,
    CrowProject,
    DocumentRole,
    ModuleRegistry,
    PricingInput,
    ProjectDocument,
    ProjectStatus,
    Provenance,
    RoundingPolicy,
)


def _ready_project(*, confirmed: bool = True) -> CrowProject:
    registry = ModuleRegistry()
    registry.register(ExamplePlugin())

    project = CrowProject(id="project-1", name="Reference Project")
    project = project.add_document(
        ProjectDocument("DRAWING", "Drawing A", DocumentRole.DRAWING, revision="B")
    )
    project = project.add_document(
        ProjectDocument("SPEC", "Technical specification", DocumentRole.SPECIFICATION, revision="B")
    )
    project = project.add_claims(
        (
            Claim(
                "drawing-size",
                "example",
                "COMPONENT-01",
                "size",
                Decimal("160"),
                "mm",
                Provenance("DRAWING"),
            ),
            Claim(
                "spec-size",
                "example",
                "COMPONENT-01",
                "size",
                Decimal("125"),
                "mm",
                Provenance("SPEC"),
            ),
        )
    )
    project = project.set_authority_policy(
        AuthorityPolicy(
            id="authority-1",
            confirmed=confirmed,
            rules=(
                AuthorityRule(
                    "AF-1.3",
                    "SPEC",
                    "DRAWING",
                    "Specification governs drawing.",
                ),
            ),
        )
    )
    project = project.enable_module("crow.example", registry)
    return project.mark_ready()


def test_project_rejects_claim_with_unknown_document() -> None:
    project = CrowProject(id="project-1", name="Project")

    with pytest.raises(ValueError, match="not active"):
        project.add_claims(
            (
                Claim(
                    "claim-1",
                    "example",
                    "COMPONENT-01",
                    "size",
                    Decimal("100"),
                    "mm",
                    Provenance("UNKNOWN"),
                ),
            )
        )


def test_project_executes_and_collects_run_and_graph() -> None:
    project = _ready_project()

    updated, run, graphs = project.execute(
        run_id="run-1",
        pricing_by_conflict_key={
            ("example", "COMPONENT-01", "size"): PricingInput(
                Decimal("500"),
                Decimal("684.20"),
                Decimal("100"),
            )
        },
        rounding=RoundingPolicy(),
    )

    assert updated.status == ProjectStatus.COMPLETED
    assert run.status == ProjectStatus.COMPLETED
    assert len(updated.runs) == 1
    assert len(graphs) == 1
    assert run.graph_ids == ("run-1:graph:1",)


def test_unconfirmed_policy_routes_project_to_review() -> None:
    project = _ready_project(confirmed=False)

    updated, run, _ = project.execute(
        run_id="run-review",
        pricing_by_conflict_key={
            ("example", "COMPONENT-01", "size"): PricingInput(
                Decimal("500"),
                Decimal("684.20"),
                Decimal("100"),
            )
        },
        rounding=RoundingPolicy(),
    )

    assert updated.status == ProjectStatus.REVIEW_REQUIRED
    assert run.status == ProjectStatus.REVIEW_REQUIRED
