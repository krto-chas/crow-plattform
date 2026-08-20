from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Literal, cast

from .engine import GraphRule

ResolutionVerificationDecision = Literal["verify_resolved", "reject_resolution"]


@dataclass(frozen=True)
class GraphAuditProfile:
    """Module-contributed graph rules and audit metadata for one domain profile."""

    profile_id: str
    audit_prefix: str
    ruleset_version: str
    rules: tuple[GraphRule, ...]
    summary_categories: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id får inte vara tomt")
        if not self.audit_prefix.strip() or ":" in self.audit_prefix:
            raise ValueError("audit_prefix måste vara ett icke-tomt prefix utan kolon")
        if not self.ruleset_version.strip():
            raise ValueError("ruleset_version får inte vara tomt")


@dataclass(frozen=True)
class GraphAuditFindingChange:
    finding_id: str
    lifecycle: str
    previous: dict[str, Any] | None
    current: dict[str, Any] | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphAuditDiffResult:
    base_audit_id: str
    target_audit_id: str
    changes: tuple[GraphAuditFindingChange, ...]
    summary: dict[str, int]
    metadata: dict[str, Any] = field(default_factory=dict)


class GraphAuditDiffer:
    """Compare immutable graph audit runs without domain-specific dependencies."""

    def compare(
        self,
        base: dict[str, Any],
        target: dict[str, Any],
        *,
        reviews: list[dict[str, Any]] | None = None,
    ) -> GraphAuditDiffResult:
        base_id = str(base.get("audit_id", ""))
        target_id = str(target.get("audit_id", ""))
        if not base_id or not target_id:
            raise ValueError("Båda granskningskörningarna måste ha audit_id")
        if base_id == target_id:
            raise ValueError("Samma granskningskörning kan inte jämföras med sig själv")

        base_findings = self._index_findings(base)
        target_findings = self._index_findings(target)
        review_index = {
            str(item.get("finding_id")): item
            for item in (reviews or [])
            if item.get("audit_id") == base_id and item.get("finding_id")
        }

        changes: list[GraphAuditFindingChange] = []
        for finding_id in sorted(set(base_findings) | set(target_findings)):
            previous = base_findings.get(finding_id)
            current = target_findings.get(finding_id)
            if previous is None:
                lifecycle = "new"
            elif current is None:
                lifecycle = "no_longer_detected"
            else:
                lifecycle = "persistent"

            metadata: dict[str, Any] = {
                "automatic_resolution_asserted": False,
                "graph_mutated": False,
            }
            review = review_index.get(finding_id)
            if review is not None:
                metadata["base_review"] = {
                    "review_id": review.get("review_id"),
                    "decision": review.get("decision"),
                    "reviewer": review.get("reviewer"),
                    "decided_at": review.get("decided_at"),
                }
            if lifecycle == "no_longer_detected":
                metadata["resolution_status"] = "candidate_for_verification"

            changes.append(
                GraphAuditFindingChange(
                    finding_id=finding_id,
                    lifecycle=lifecycle,
                    previous=previous,
                    current=current,
                    metadata=metadata,
                )
            )

        summary = {
            "total": len(changes),
            "new": sum(item.lifecycle == "new" for item in changes),
            "persistent": sum(item.lifecycle == "persistent" for item in changes),
            "no_longer_detected": sum(item.lifecycle == "no_longer_detected" for item in changes),
        }
        return GraphAuditDiffResult(
            base_audit_id=base_id,
            target_audit_id=target_id,
            changes=tuple(changes),
            summary=summary,
            metadata={
                "comparison_only": True,
                "automatic_resolution_performed": False,
                "audit_runs_mutated": False,
            },
        )

    @staticmethod
    def _index_findings(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
        findings = audit.get("findings", [])
        if not isinstance(findings, list):
            raise ValueError("Ogiltig findings-lista i granskningskörning")
        indexed: dict[str, dict[str, Any]] = {}
        for finding in findings:
            if not isinstance(finding, dict) or not finding.get("finding_id"):
                raise ValueError("Varje finding måste ha finding_id")
            finding_id = str(finding["finding_id"])
            if finding_id in indexed:
                raise ValueError(f"Duplicerat finding_id: {finding_id}")
            indexed[finding_id] = finding
        return indexed


@dataclass(frozen=True)
class GraphResolutionVerification:
    verification_id: str
    base_audit_id: str
    target_audit_id: str
    finding_id: str
    decision: ResolutionVerificationDecision
    reviewer: str
    rationale: str
    decided_at: str
    previous_finding: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


class GraphResolutionVerificationService:
    """Record a human resolution decision without importing a domain module."""

    def __init__(self, namespace: str = "graph") -> None:
        namespace = namespace.strip()
        if not namespace or ":" in namespace:
            raise ValueError("namespace måste vara ett icke-tomt prefix utan kolon")
        self._namespace = namespace

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
    ) -> GraphResolutionVerification:
        if lifecycle != "no_longer_detected":
            raise ValueError("Endast findings som inte längre upptäcks kan verifieras")
        if previous_finding is None:
            raise ValueError("Ursprunglig finding saknas")
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
        return GraphResolutionVerification(
            verification_id=f"{self._namespace}:resolution-verification:{digest}",
            base_audit_id=base_audit_id,
            target_audit_id=target_audit_id,
            finding_id=finding_id,
            decision=cast(ResolutionVerificationDecision, decision),
            reviewer=reviewer,
            rationale=rationale,
            decided_at=timestamp,
            previous_finding=dict(previous_finding),
            metadata={
                "human_verification": True,
                "automatic_resolution_performed": False,
                "audit_runs_mutated": False,
                "graph_mutated": False,
            },
        )
