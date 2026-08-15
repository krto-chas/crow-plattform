from crow_claim_extraction import (
    ClaimCandidate,
    ClaimCandidateCollection,
    ClaimCandidateStatus,
    ClaimCandidateType,
    ClaimProvenance,
)
from crow_knowledge_fusion import FusionStatus, fuse_claim_candidates


def candidate(
    candidate_id: str,
    document_id: str,
    subject: str,
    value: str,
    unit: str = "L/S",
    confidence: float = 0.9,
) -> ClaimCandidate:
    provenance = ClaimProvenance(
        observation_ids=(f"obs:{candidate_id}",),
        document_id=document_id,
        page_number=1,
        region_id=f"region:{document_id}",
        locator_values=(f"{document_id}#page=1",),
    )
    return ClaimCandidate(
        id=candidate_id,
        candidate_type=ClaimCandidateType.KEY_VALUE,
        subject=subject,
        predicate="has_value",
        value=value,
        normalized_value=value,
        unit=unit,
        confidence=confidence,
        status=ClaimCandidateStatus.PROPOSED,
        provenance=provenance,
        fingerprint=f"fingerprint:{candidate_id}",
    )


def test_single_candidate_becomes_singleton() -> None:
    result = fuse_claim_candidates(
        ClaimCandidateCollection(
            project_id="project",
            candidates=(candidate("c1", "doc1", "Luftflöde", "320"),),
        )
    )

    assert result.clusters[0].status == FusionStatus.SINGLETON


def test_equal_values_become_consistent_cluster() -> None:
    result = fuse_claim_candidates(
        ClaimCandidateCollection(
            project_id="project",
            candidates=(
                candidate("c1", "doc1", "Luftflöde", "320"),
                candidate("c2", "doc2", "luftflöde", "320"),
            ),
        )
    )

    cluster = result.clusters[0]
    assert cluster.status == FusionStatus.CONSISTENT
    assert cluster.support_count == 2
    assert cluster.document_ids == ("doc1", "doc2")
    assert len(cluster.variants) == 1


def test_different_values_become_conflicting_cluster() -> None:
    result = fuse_claim_candidates(
        ClaimCandidateCollection(
            project_id="project",
            candidates=(
                candidate("c1", "doc1", "Luftflöde", "320"),
                candidate("c2", "doc2", "Luftflöde", "400"),
            ),
        )
    )

    cluster = result.clusters[0]
    assert cluster.status == FusionStatus.CONFLICTING
    assert len(cluster.variants) == 2


def test_different_units_do_not_share_cluster() -> None:
    result = fuse_claim_candidates(
        ClaimCandidateCollection(
            project_id="project",
            candidates=(
                candidate("c1", "doc1", "Dimension", "160", "MM"),
                candidate("c2", "doc2", "Dimension", "160", "CM"),
            ),
        )
    )

    assert len(result.clusters) == 2


def test_fusion_is_stable() -> None:
    collection = ClaimCandidateCollection(
        project_id="project",
        candidates=(
            candidate("c1", "doc1", "Luftflöde", "320"),
            candidate("c2", "doc2", "Luftflöde", "320"),
        ),
    )

    assert fuse_claim_candidates(collection) == fuse_claim_candidates(collection)
