from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Literal, cast

EvidenceResolutionVerificationDecision = Literal[
    "verify_resolved",
    "reject_resolution",
]


@dataclass(frozen=True)
class EvidenceResolutionVerification:
    verification_id: str
    base_audit_id: str
    target_audit_id: str
    finding_id: str
    decision: EvidenceResolutionVerificationDecision
    reviewer: str
    rationale: str
    decided_at: str
    previous_finding: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


class EvidenceResolutionVerificationService:
    """Record a human decision for an evidence finding no longer detected."""

    def decide(
        self,
        *,
        base_audit_id: str,
        target_audit_id: str,
        finding_id: str,
        lifecycle: str,
        previous_finding: dict[str, Any] | None,
        decision: str,
        reviewer: str,
        rationale: str,
        decided_at: str | None = None,
    ) -> EvidenceResolutionVerification:
        if lifecycle != "no_longer_detected":
            raise ValueError("Endast findings som inte längre upptäcks kan verifieras")
        if previous_finding is None:
            raise ValueError("Ursprunglig evidence finding saknas")
        if decision not in ("verify_resolved", "reject_resolution"):
            raise ValueError("Ogiltigt verifieringsbeslut")
        reviewer = reviewer.strip()
        rationale = rationale.strip()
        if not reviewer:
            raise ValueError("Granskare måste anges")
        if not rationale:
            raise ValueError("Motivering måste anges")
        timestamp = decided_at or datetime.now(UTC).isoformat()
        key = "|".join(
            (
                base_audit_id,
                target_audit_id,
                finding_id,
                decision,
                reviewer,
                timestamp,
            )
        )
        digest = sha256(key.encode("utf-8")).hexdigest()[:20]
        return EvidenceResolutionVerification(
            verification_id=f"evidence:resolution-verification:{digest}",
            base_audit_id=base_audit_id,
            target_audit_id=target_audit_id,
            finding_id=finding_id,
            decision=cast(EvidenceResolutionVerificationDecision, decision),
            reviewer=reviewer,
            rationale=rationale,
            decided_at=timestamp,
            previous_finding=dict(previous_finding),
            metadata={
                "human_verification": True,
                "automatic_resolution_performed": False,
                "audit_runs_mutated": False,
                "graph_mutated": False,
                "evidence_mutated": False,
            },
        )
