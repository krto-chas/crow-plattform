from crow_claim_extraction import (
    ClaimCandidate,
    ClaimCandidateCollection,
    ClaimCandidateStatus,
    ClaimCandidateType,
    ClaimProvenance,
)
from crow_knowledge_fusion import fuse_claim_candidates, summarize_fusion


def claim(cid, doc, subject, value):
    provenance = ClaimProvenance(
        observation_ids=(f"obs:{cid}",),
        document_id=doc,
        page_number=1,
        region_id=f"region:{doc}",
        locator_values=(f"{doc}#page=1",),
    )
    return ClaimCandidate(
        id=cid,
        candidate_type=ClaimCandidateType.KEY_VALUE,
        subject=subject,
        predicate="has_value",
        value=value,
        normalized_value=value,
        unit="L/S",
        confidence=0.9,
        status=ClaimCandidateStatus.PROPOSED,
        provenance=provenance,
        fingerprint=f"fp:{cid}",
    )


collection = ClaimCandidateCollection(
    project_id="demo",
    candidates=(
        claim("c1", "drawing", "Luftflöde", "320"),
        claim("c2", "description", "Luftflöde", "320"),
        claim("c3", "schedule", "Luftflöde", "400"),
        claim("c4", "drawing", "Frånluft", "250"),
    ),
)
result = fuse_claim_candidates(collection)
print(summarize_fusion(result))
