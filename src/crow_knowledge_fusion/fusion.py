from __future__ import annotations

import hashlib
from collections import defaultdict

from crow_claim_extraction import ClaimCandidate, ClaimCandidateCollection

from .models import (
    FusionStatus,
    KnowledgeCluster,
    KnowledgeFusionResult,
    ValueVariant,
)


def _canonical(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def semantic_key(candidate: ClaimCandidate) -> str:
    return "|".join(
        [
            candidate.candidate_type.value,
            _canonical(candidate.subject),
            _canonical(candidate.predicate),
            (candidate.unit or "").casefold(),
        ]
    )


def _cluster_fingerprint(key: str, candidates: tuple[ClaimCandidate, ...]) -> str:
    material = key + "|" + "|".join(sorted(candidate.fingerprint for candidate in candidates))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _cluster_id(fingerprint: str) -> str:
    return "knowledge-cluster:" + fingerprint


def _variant(
    normalized_value: str,
    unit: str | None,
    candidates: tuple[ClaimCandidate, ...],
) -> ValueVariant:
    confidences = [candidate.confidence for candidate in candidates]
    return ValueVariant(
        normalized_value=normalized_value,
        unit=unit,
        candidate_ids=tuple(sorted(candidate.id for candidate in candidates)),
        document_ids=tuple(sorted({candidate.provenance.document_id for candidate in candidates})),
        confidence_max=max(confidences),
        confidence_mean=round(sum(confidences) / len(confidences), 4),
    )


def fuse_claim_candidates(
    collection: ClaimCandidateCollection,
) -> KnowledgeFusionResult:
    grouped: dict[str, list[ClaimCandidate]] = defaultdict(list)
    for candidate in collection.candidates:
        grouped[semantic_key(candidate)].append(candidate)

    clusters: list[KnowledgeCluster] = []
    for key, members_list in grouped.items():
        members = tuple(sorted(members_list, key=lambda item: item.id))
        by_value: dict[tuple[str, str | None], list[ClaimCandidate]] = defaultdict(list)
        for candidate in members:
            by_value[(candidate.normalized_value, candidate.unit)].append(candidate)

        variants = tuple(
            sorted(
                (
                    _variant(value, unit, tuple(candidates))
                    for (value, unit), candidates in by_value.items()
                ),
                key=lambda item: (item.normalized_value, item.unit or ""),
            )
        )

        if len(members) == 1:
            status = FusionStatus.SINGLETON
        elif len(variants) == 1:
            status = FusionStatus.CONSISTENT
        else:
            status = FusionStatus.CONFLICTING

        first = members[0]
        fingerprint = _cluster_fingerprint(key, members)
        clusters.append(
            KnowledgeCluster(
                id=_cluster_id(fingerprint),
                semantic_key=key,
                subject=first.subject,
                predicate=first.predicate,
                unit=first.unit,
                candidate_ids=tuple(candidate.id for candidate in members),
                document_ids=tuple(
                    sorted({candidate.provenance.document_id for candidate in members})
                ),
                variants=variants,
                status=status,
                support_count=len(members),
                fingerprint=fingerprint,
            )
        )

    return KnowledgeFusionResult(
        project_id=collection.project_id,
        clusters=tuple(sorted(clusters, key=lambda item: item.semantic_key)),
    )
