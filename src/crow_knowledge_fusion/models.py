from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FusionStatus(StrEnum):
    SINGLETON = "singleton"
    CONSISTENT = "consistent"
    CONFLICTING = "conflicting"


@dataclass(frozen=True, slots=True)
class ValueVariant:
    normalized_value: str
    unit: str | None
    candidate_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    confidence_max: float
    confidence_mean: float


@dataclass(frozen=True, slots=True)
class KnowledgeCluster:
    id: str
    semantic_key: str
    subject: str
    predicate: str
    unit: str | None
    candidate_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    variants: tuple[ValueVariant, ...]
    status: FusionStatus
    support_count: int
    fingerprint: str


@dataclass(frozen=True, slots=True)
class KnowledgeFusionResult:
    project_id: str
    clusters: tuple[KnowledgeCluster, ...] = ()

    @property
    def conflicting_count(self) -> int:
        return sum(cluster.status == FusionStatus.CONFLICTING for cluster in self.clusters)

    @property
    def consistent_count(self) -> int:
        return sum(cluster.status == FusionStatus.CONSISTENT for cluster in self.clusters)

    @property
    def singleton_count(self) -> int:
        return sum(cluster.status == FusionStatus.SINGLETON for cluster in self.clusters)
