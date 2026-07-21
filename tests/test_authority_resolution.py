from datetime import date

from crow_authority import (
    AuthorityDecisionStatus,
    DocumentAuthorityMetadata,
    DocumentAuthorityType,
    ab04_framework,
    resolve_authority,
)
from crow_knowledge_fusion import (
    FusionStatus,
    KnowledgeCluster,
    KnowledgeFusionResult,
    ValueVariant,
)


def variant(value: str, document_id: str) -> ValueVariant:
    return ValueVariant(
        normalized_value=value,
        unit="L/S",
        candidate_ids=(f"candidate:{document_id}",),
        document_ids=(document_id,),
        confidence_max=0.9,
        confidence_mean=0.9,
    )


def cluster(
    status: FusionStatus,
    variants: tuple[ValueVariant, ...],
) -> KnowledgeCluster:
    return KnowledgeCluster(
        id="cluster:1",
        semantic_key="key_value|luftflöde|has_value|l/s",
        subject="Luftflöde",
        predicate="has_value",
        unit="L/S",
        candidate_ids=tuple(candidate for item in variants for candidate in item.candidate_ids),
        document_ids=tuple(document for item in variants for document in item.document_ids),
        variants=variants,
        status=status,
        support_count=len(variants),
        fingerprint="cluster-fingerprint",
    )


def test_singleton_is_complementary_not_conflicting() -> None:
    fusion = KnowledgeFusionResult(
        project_id="project",
        clusters=(cluster(FusionStatus.SINGLETON, (variant("320", "drawing"),)),),
    )

    result = resolve_authority(fusion, ab04_framework(), ())

    assert result.decisions[0].status == (AuthorityDecisionStatus.ACCEPTED_COMPLEMENTARY)
    assert result.decisions[0].accepted_value == "320"


def test_description_wins_over_drawing() -> None:
    fusion = KnowledgeFusionResult(
        project_id="project",
        clusters=(
            cluster(
                FusionStatus.CONFLICTING,
                (variant("320", "drawing"), variant("400", "description")),
            ),
        ),
    )
    metadata = (
        DocumentAuthorityMetadata(
            "drawing",
            DocumentAuthorityType.DRAWING,
        ),
        DocumentAuthorityMetadata(
            "description",
            DocumentAuthorityType.TECHNICAL_DESCRIPTION,
        ),
    )

    result = resolve_authority(fusion, ab04_framework(), metadata)
    decision = result.decisions[0]

    assert decision.status == AuthorityDecisionStatus.RESOLVED_BY_HIERARCHY
    assert decision.accepted_value == "400"
    assert decision.accepted_document_ids == ("description",)


def test_latest_date_wins_within_same_group() -> None:
    fusion = KnowledgeFusionResult(
        project_id="project",
        clusters=(
            cluster(
                FusionStatus.CONFLICTING,
                (variant("320", "drawing-old"), variant("400", "drawing-new")),
            ),
        ),
    )
    metadata = (
        DocumentAuthorityMetadata(
            "drawing-old",
            DocumentAuthorityType.DRAWING,
            issue_date=date(2026, 1, 1),
        ),
        DocumentAuthorityMetadata(
            "drawing-new",
            DocumentAuthorityType.DRAWING,
            issue_date=date(2026, 2, 1),
        ),
    )

    decision = resolve_authority(fusion, ab04_framework(), metadata).decisions[0]

    assert decision.status == AuthorityDecisionStatus.RESOLVED_BY_DATE
    assert decision.accepted_value == "400"


def test_missing_metadata_requires_review() -> None:
    fusion = KnowledgeFusionResult(
        project_id="project",
        clusters=(
            cluster(
                FusionStatus.CONFLICTING,
                (variant("320", "known"), variant("400", "unknown")),
            ),
        ),
    )
    metadata = (
        DocumentAuthorityMetadata(
            "known",
            DocumentAuthorityType.DRAWING,
        ),
    )

    decision = resolve_authority(fusion, ab04_framework(), metadata).decisions[0]

    assert decision.status == (AuthorityDecisionStatus.UNRESOLVED_MISSING_METADATA)


def test_same_rank_same_date_remains_unresolved() -> None:
    fusion = KnowledgeFusionResult(
        project_id="project",
        clusters=(
            cluster(
                FusionStatus.CONFLICTING,
                (variant("320", "drawing-a"), variant("400", "drawing-b")),
            ),
        ),
    )
    metadata = (
        DocumentAuthorityMetadata(
            "drawing-a",
            DocumentAuthorityType.DRAWING,
            issue_date=date(2026, 2, 1),
        ),
        DocumentAuthorityMetadata(
            "drawing-b",
            DocumentAuthorityType.DRAWING,
            issue_date=date(2026, 2, 1),
        ),
    )

    decision = resolve_authority(fusion, ab04_framework(), metadata).decisions[0]

    assert decision.status == AuthorityDecisionStatus.UNRESOLVED_TIE
