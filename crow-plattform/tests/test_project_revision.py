from decimal import Decimal

from crow_module_sdk import (
    Claim,
    CrowProject,
    DocumentRole,
    ProjectDocument,
    ProjectStatus,
    Provenance,
)


def test_document_revision_invalidates_source_claims() -> None:
    project = CrowProject.create("project-1", "Project")
    project = project.add_document(
        ProjectDocument("SPEC", "Specification", DocumentRole.SPECIFICATION, "A", "old")
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
                Provenance("SPEC", "A"),
            ),
        )
    )

    result = project.revise_document("SPEC", revision="B", checksum="new")

    assert result.invalidated_claim_ids == ("claim-1",)
    assert result.project.invalidated_claim_ids == ("claim-1",)
    assert result.project.status == ProjectStatus.DRAFT
    assert result.project.audit_events[-1].event_type.value == "sources_invalidated"


def test_replacing_revised_document_claims_clears_invalidation() -> None:
    project = CrowProject.create("project-1", "Project")
    project = project.add_document(
        ProjectDocument("SPEC", "Specification", DocumentRole.SPECIFICATION, "A", "old")
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
                Provenance("SPEC", "A"),
            ),
        )
    )
    revised = project.revise_document("SPEC", revision="B", checksum="new").project

    updated = revised.replace_claims_for_document(
        "SPEC",
        (
            Claim(
                "claim-2",
                "example",
                "COMPONENT-01",
                "size",
                Decimal("130"),
                "mm",
                Provenance("SPEC", "B"),
            ),
        ),
    )

    assert updated.invalidated_claim_ids == ()
    assert tuple(claim.id for claim in updated.claims) == ("claim-2",)
