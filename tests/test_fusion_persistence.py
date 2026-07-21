from pathlib import Path

from crow_claim_extraction import (
    ClaimCandidate,
    ClaimCandidateCollection,
    ClaimCandidateStatus,
    ClaimCandidateType,
    ClaimProvenance,
)
from crow_knowledge_fusion import (
    fuse_claim_candidates,
    load_fusion_result,
    save_fusion_result,
)


def test_fusion_result_round_trip(tmp_path: Path) -> None:
    provenance = ClaimProvenance(
        observation_ids=("obs:1",),
        document_id="doc:1",
        page_number=1,
        region_id="region:1",
        locator_values=("doc:1#page=1",),
    )
    claim = ClaimCandidate(
        id="claim:1",
        candidate_type=ClaimCandidateType.KEY_VALUE,
        subject="Tryck",
        predicate="has_value",
        value="200",
        normalized_value="200",
        unit="PA",
        confidence=0.9,
        status=ClaimCandidateStatus.PROPOSED,
        provenance=provenance,
        fingerprint="claim-fingerprint",
    )
    result = fuse_claim_candidates(
        ClaimCandidateCollection(project_id="project", candidates=(claim,))
    )
    path = tmp_path / "fusion.json"

    save_fusion_result(result, path)

    assert load_fusion_result(path) == result
