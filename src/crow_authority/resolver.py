from __future__ import annotations

import hashlib

from crow_knowledge_fusion import (
    FusionStatus,
    KnowledgeCluster,
    KnowledgeFusionResult,
    ValueVariant,
)

from .models import (
    AuthorityDecision,
    AuthorityDecisionStatus,
    AuthorityFramework,
    AuthorityResolution,
    DocumentAuthorityMetadata,
    EvaluatedVariant,
)


def _rank_map(framework: AuthorityFramework) -> dict[object, int]:
    return {document_type: rank for rank, document_type in enumerate(framework.hierarchy, start=1)}


def _variant_metadata(
    variant: ValueVariant,
    metadata: dict[str, DocumentAuthorityMetadata],
    ranks: dict[object, int],
) -> EvaluatedVariant:
    documents = [
        metadata[document_id] for document_id in variant.document_ids if document_id in metadata
    ]
    best_rank = min(
        (ranks[item.authority_type] for item in documents),
        default=None,
    )
    latest_date = max(
        (item.issue_date for item in documents if item.issue_date is not None),
        default=None,
    )
    return EvaluatedVariant(
        normalized_value=variant.normalized_value,
        unit=variant.unit,
        candidate_ids=variant.candidate_ids,
        document_ids=variant.document_ids,
        best_rank=best_rank,
        latest_date=latest_date,
    )


def _decision_id(cluster_id: str, status: AuthorityDecisionStatus, value: str | None) -> str:
    material = "|".join([cluster_id, status.value, value or ""])
    return "authority-decision:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _accepted(
    cluster: KnowledgeCluster,
    status: AuthorityDecisionStatus,
    variant: EvaluatedVariant,
    framework: AuthorityFramework,
    applied_rule: str,
    explanation: str,
    trace: tuple[str, ...],
    evaluated: tuple[EvaluatedVariant, ...],
) -> AuthorityDecision:
    return AuthorityDecision(
        id=_decision_id(cluster.id, status, variant.normalized_value),
        cluster_id=cluster.id,
        status=status,
        accepted_value=variant.normalized_value,
        accepted_unit=variant.unit,
        accepted_candidate_ids=variant.candidate_ids,
        accepted_document_ids=variant.document_ids,
        evaluated_variants=evaluated,
        applied_rule=applied_rule,
        explanation=explanation,
        framework_id=framework.id,
        trace=trace,
    )


def _unresolved(
    cluster: KnowledgeCluster,
    status: AuthorityDecisionStatus,
    framework: AuthorityFramework,
    applied_rule: str,
    explanation: str,
    trace: tuple[str, ...],
    evaluated: tuple[EvaluatedVariant, ...],
) -> AuthorityDecision:
    return AuthorityDecision(
        id=_decision_id(cluster.id, status, None),
        cluster_id=cluster.id,
        status=status,
        accepted_value=None,
        accepted_unit=None,
        accepted_candidate_ids=(),
        accepted_document_ids=(),
        evaluated_variants=evaluated,
        applied_rule=applied_rule,
        explanation=explanation,
        framework_id=framework.id,
        trace=trace,
    )


def resolve_cluster(
    cluster: KnowledgeCluster,
    framework: AuthorityFramework,
    metadata: dict[str, DocumentAuthorityMetadata],
) -> AuthorityDecision:
    ranks = _rank_map(framework)
    evaluated = tuple(_variant_metadata(variant, metadata, ranks) for variant in cluster.variants)

    if cluster.status == FusionStatus.SINGLETON:
        variant = evaluated[0]
        return _accepted(
            cluster,
            AuthorityDecisionStatus.ACCEPTED_COMPLEMENTARY,
            variant,
            framework,
            "complementary_information",
            "Uppgiften förekommer endast i en handling och motsägs inte av någon annan.",
            (
                "Cluster status: singleton",
                "No contradictory value variant found",
                "Information retained as complementary",
            ),
            evaluated,
        )

    if cluster.status == FusionStatus.CONSISTENT:
        variant = evaluated[0]
        return _accepted(
            cluster,
            AuthorityDecisionStatus.ACCEPTED_CONSISTENT,
            variant,
            framework,
            "consistent_sources",
            "Flera handlingar stödjer samma normaliserade värde.",
            (
                "Cluster status: consistent",
                f"Supporting candidates: {cluster.support_count}",
                "Common value accepted",
            ),
            evaluated,
        )

    if any(variant.best_rank is None for variant in evaluated):
        return _unresolved(
            cluster,
            AuthorityDecisionStatus.UNRESOLVED_MISSING_METADATA,
            framework,
            "authority_metadata_required",
            "Minst en motstridig variant saknar dokumentklassning och kan inte rangordnas.",
            (
                "Cluster status: conflicting",
                "Document authority metadata incomplete",
                "Human review required",
            ),
            evaluated,
        )

    best_rank = min(variant.best_rank for variant in evaluated if variant.best_rank is not None)
    hierarchy_winners = tuple(variant for variant in evaluated if variant.best_rank == best_rank)

    if len(hierarchy_winners) == 1:
        winner = hierarchy_winners[0]
        return _accepted(
            cluster,
            AuthorityDecisionStatus.RESOLVED_BY_HIERARCHY,
            winner,
            framework,
            "document_hierarchy",
            "Den högst rangordnade handlingstypen avgör den motstridiga uppgiften.",
            (
                "Cluster status: conflicting",
                f"Best authority rank: {best_rank}",
                f"Accepted value: {winner.normalized_value}",
            ),
            evaluated,
        )

    dated = tuple(variant for variant in hierarchy_winners if variant.latest_date is not None)
    if dated:
        latest = max(variant.latest_date for variant in dated if variant.latest_date is not None)
        date_winners = tuple(variant for variant in dated if variant.latest_date == latest)
        if len(date_winners) == 1:
            winner = date_winners[0]
            return _accepted(
                cluster,
                AuthorityDecisionStatus.RESOLVED_BY_DATE,
                winner,
                framework,
                "latest_date_within_same_rank",
                "Motstridigheten ligger inom samma rang; senast daterad handling gäller.",
                (
                    "Cluster status: conflicting",
                    f"Tied authority rank: {best_rank}",
                    f"Latest issue date: {latest.isoformat()}",
                    f"Accepted value: {winner.normalized_value}",
                ),
                evaluated,
            )

    return _unresolved(
        cluster,
        AuthorityDecisionStatus.UNRESOLVED_TIE,
        framework,
        "same_rank_tie",
        "Varianterna har samma rang och kan inte särskiljas säkert med tillgängligt datum.",
        (
            "Cluster status: conflicting",
            f"Tied authority rank: {best_rank}",
            "Human review required",
        ),
        evaluated,
    )


def resolve_authority(
    fusion: KnowledgeFusionResult,
    framework: AuthorityFramework,
    documents: tuple[DocumentAuthorityMetadata, ...],
) -> AuthorityResolution:
    metadata = {item.document_id: item for item in documents}
    decisions = tuple(resolve_cluster(cluster, framework, metadata) for cluster in fusion.clusters)
    return AuthorityResolution(
        project_id=fusion.project_id,
        framework=framework,
        decisions=decisions,
    )
