from decimal import Decimal
from pathlib import Path

from crow_module_sdk import (
    AuthorityPolicy,
    AuthorityRule,
    Claim,
    CrowProject,
    DocumentRole,
    JsonProjectRepository,
    ProjectDocument,
    Provenance,
)


def test_project_round_trips_through_json_repository(tmp_path: Path) -> None:
    project = CrowProject(id="project-1", name="Project")
    project = project.add_document(
        ProjectDocument("SPEC", "Specification", DocumentRole.SPECIFICATION, revision="A")
    )
    project = project.add_claims(
        (
            Claim(
                "claim-1",
                "example",
                "COMPONENT-01",
                "size",
                Decimal("125"),
                "mm",
                Provenance("SPEC", "A", 7, "3.2"),
            ),
        )
    )
    project = project.set_authority_policy(
        AuthorityPolicy(
            "authority-1",
            (AuthorityRule("AF-1", "SPEC", "DRAWING", "Specification first."),),
            True,
        )
    )

    repository = JsonProjectRepository(tmp_path / "projects")
    repository.save(project)
    loaded = repository.load("project-1")

    assert loaded is not None
    assert loaded.id == project.id
    assert loaded.documents == project.documents
    assert loaded.claims == project.claims
    assert loaded.authority_policy == project.authority_policy
