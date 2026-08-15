from __future__ import annotations

import hashlib

from crow_authority import (
    AuthorityDecision,
    AuthorityDecisionStatus,
    AuthorityResolution,
)
from crow_knowledge_fusion import KnowledgeCluster, KnowledgeFusionResult

from .models import (
    AcceptanceBasis,
    AcceptedClaim,
    AcceptedClaimProvenance,
    AcceptedClaimSet,
    PendingClaim,
)

_ACCEPTED_STATUSES = {
    AuthorityDecisionStatus.ACCEPTED_COMPLEMENTARY,
    AuthorityDecisionStatus.ACCEPTED_CONSISTENT,
    AuthorityDecisionStatus.RESOLVED_BY_HIERARCHY,
    AuthorityDecisionStatus.RESOLVED_BY_DATE,
}

_BASIS = {
    AuthorityDecisionStatus.ACCEPTED_COMPLEMENTARY: AcceptanceBasis.COMPLEMENTARY,
    AuthorityDecisionStatus.ACCEPTED_CONSISTENT: AcceptanceBasis.CONSENSUS,
    AuthorityDecisionStatus.RESOLVED_BY_HIERARCHY: AcceptanceBasis.AUTHORITY_HIERARCHY,
    AuthorityDecisionStatus.RESOLVED_BY_DATE: AcceptanceBasis.LATEST_DATE,
}


def _fingerprint(cluster: KnowledgeCluster, decision: AuthorityDecision) -> str:
    material = "|".join(
        (
            cluster.semantic_key,
            decision.accepted_value or "",
            decision.accepted_unit or "",
            decision.id,
            cluster.fingerprint,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _confidence(cluster: KnowledgeCluster, decision: AuthorityDecision) -> float:
    accepted = set(decision.accepted_candidate_ids)
    values = [
        variant.confidence_mean
        for variant in cluster.variants
        if accepted.intersection(variant.candidate_ids)
    ]
    return round(max(values, default=0.0), 6)


def _claim(cluster: KnowledgeCluster, decision: AuthorityDecision) -> AcceptedClaim:
    if decision.accepted_value is None:
        raise ValueError("Accepted authority decision has no accepted value")
    fingerprint = _fingerprint(cluster, decision)
    return AcceptedClaim(
        id=f"accepted-claim:{fingerprint}",
        semantic_key=cluster.semantic_key,
        subject=cluster.subject,
        predicate=cluster.predicate,
        value=decision.accepted_value,
        unit=decision.accepted_unit,
        confidence=_confidence(cluster, decision),
        acceptance_basis=_BASIS[decision.status],
        provenance=AcceptedClaimProvenance(
            cluster_id=cluster.id,
            authority_decision_id=decision.id,
            candidate_ids=decision.accepted_candidate_ids,
            document_ids=decision.accepted_document_ids,
            framework_id=decision.framework_id,
            applied_rule=decision.applied_rule,
            trace=decision.trace,
        ),
        fingerprint=fingerprint,
    )


def canonicalize_claims(
    fusion: KnowledgeFusionResult,
    resolution: AuthorityResolution,
) -> AcceptedClaimSet:
    if fusion.project_id != resolution.project_id:
        raise ValueError("Fusion and authority resolution belong to different projects")

    clusters = {cluster.id: cluster for cluster in fusion.clusters}
    claims: list[AcceptedClaim] = []
    pending: list[PendingClaim] = []
    seen_clusters: set[str] = set()

    for decision in sorted(resolution.decisions, key=lambda item: item.cluster_id):
        if decision.cluster_id in seen_clusters:
            raise ValueError(f"Duplicate authority decision for {decision.cluster_id}")
        seen_clusters.add(decision.cluster_id)
        cluster = clusters.get(decision.cluster_id)
        if cluster is None:
            raise ValueError(f"Authority decision references unknown cluster {decision.cluster_id}")
        if decision.status in _ACCEPTED_STATUSES:
            claims.append(_claim(cluster, decision))
        else:
            pending.append(
                PendingClaim(
                    cluster_id=cluster.id,
                    authority_decision_id=decision.id,
                    reason=decision.explanation,
                    status=decision.status.value,
                )
            )

    missing = sorted(set(clusters) - seen_clusters)
    pending.extend(
        PendingClaim(
            cluster_id=cluster_id,
            authority_decision_id="",
            reason="No authority decision exists for this knowledge cluster.",
            status="missing_authority_decision",
        )
        for cluster_id in missing
    )
    return AcceptedClaimSet(
        project_id=fusion.project_id,
        claims=tuple(sorted(claims, key=lambda item: item.id)),
        pending=tuple(sorted(pending, key=lambda item: item.cluster_id)),
    )
