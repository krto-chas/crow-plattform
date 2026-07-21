from decimal import Decimal

import pytest
from crow_example_module import ExamplePlugin

from crow_module_sdk import (
    AuthorityPolicy,
    AuthorityRule,
    Claim,
    CrowProject,
    DocumentRole,
    InMemoryProjectUnitOfWork,
    ModuleRegistry,
    PricingInput,
    ProjectDocument,
    Provenance,
    RoundingPolicy,
    execute_project_transactionally,
)


def _project() -> CrowProject:
    registry = ModuleRegistry()
    registry.register(ExamplePlugin())
    project = CrowProject.create("project-1", "Project")
    project = project.add_document(ProjectDocument("DRAWING", "Drawing", DocumentRole.DRAWING))
    project = project.add_document(
        ProjectDocument("SPEC", "Specification", DocumentRole.SPECIFICATION)
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
            "policy",
            (AuthorityRule("AF-1", "SPEC", "DRAWING", "Specification first."),),
            True,
        )
    )
    return project.enable_module("crow.example", registry).mark_ready()


def test_transaction_commits_project_and_graphs_together() -> None:
    unit_of_work = InMemoryProjectUnitOfWork()

    result = execute_project_transactionally(
        _project(),
        run_id="run-1",
        pricing_by_conflict_key={
            ("example", "COMPONENT-01", "size"): PricingInput(
                Decimal("500"), Decimal("684.20"), Decimal("100")
            )
        },
        rounding=RoundingPolicy(),
        unit_of_work=unit_of_work,
    )

    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0
    assert unit_of_work.projects["project-1"] == result.project
    assert "run-1:graph:1" in unit_of_work.graphs


def test_transaction_rolls_back_everything_on_commit_failure() -> None:
    unit_of_work = InMemoryProjectUnitOfWork(fail_on_commit=True)

    with pytest.raises(RuntimeError, match="commit failure"):
        execute_project_transactionally(
            _project(),
            run_id="run-1",
            pricing_by_conflict_key={
                ("example", "COMPONENT-01", "size"): PricingInput(
                    Decimal("500"), Decimal("684.20"), Decimal("100")
                )
            },
            rounding=RoundingPolicy(),
            unit_of_work=unit_of_work,
        )

    assert unit_of_work.projects == {}
    assert unit_of_work.graphs == {}
    assert unit_of_work.rollbacks == 1
