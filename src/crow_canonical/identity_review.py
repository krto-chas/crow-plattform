from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256

from .models import CanonicalRelation


class IdentityReviewDecision(StrEnum):
    CONFIRM_SAME = "confirm_same"
    REJECT_SAME = "reject_same"


@dataclass(frozen=True)
class IdentityReview:
    review_id: str
    candidate_relation_id: str
    decision: IdentityReviewDecision
    reviewer: str
    rationale: str
    decided_at: str


@dataclass(frozen=True)
class IdentityReviewResult:
    review: IdentityReview
    resolved_relation: CanonicalRelation


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"ccm:{prefix}:{digest}"


class IdentityReviewService:
    """Resolve a same-as candidate without deleting or merging source observations."""

    def decide(
        self,
        candidate: CanonicalRelation,
        *,
        decision: IdentityReviewDecision,
        reviewer: str,
        rationale: str,
        decided_at: str | None = None,
    ) -> IdentityReviewResult:
        if candidate.relation_type != "same_as_candidate":
            raise ValueError("identity review requires a same_as_candidate relation")
        if candidate.metadata.get("status") != "review_required":
            raise ValueError("identity candidate is not marked review_required")
        if not reviewer.strip():
            raise ValueError("reviewer must not be empty")
        if not rationale.strip():
            raise ValueError("rationale must not be empty")

        timestamp = decided_at or datetime.now(UTC).isoformat()
        review = IdentityReview(
            review_id=_stable_id(
                "identity-review",
                candidate.canonical_id,
                decision.value,
                reviewer.strip(),
                timestamp,
            ),
            candidate_relation_id=candidate.canonical_id,
            decision=decision,
            reviewer=reviewer.strip(),
            rationale=rationale.strip(),
            decided_at=timestamp,
        )
        relation_type = (
            "same_as_confirmed"
            if decision is IdentityReviewDecision.CONFIRM_SAME
            else "not_same_as"
        )
        resolved = CanonicalRelation(
            canonical_id=_stable_id(
                "relation",
                candidate.source_id,
                relation_type,
                candidate.target_id,
                review.review_id,
            ),
            source_id=candidate.source_id,
            relation_type=relation_type,
            target_id=candidate.target_id,
            confidence=candidate.confidence,
            evidence=candidate.evidence,
            metadata={
                **candidate.metadata,
                "status": "reviewed",
                "candidate_relation_id": candidate.canonical_id,
                "review_id": review.review_id,
                "decision": decision.value,
                "reviewer": review.reviewer,
                "rationale": review.rationale,
                "decided_at": review.decided_at,
                "source_observations_preserved": True,
                "automatic_merge_performed": False,
            },
        )
        return IdentityReviewResult(review=review, resolved_relation=resolved)
