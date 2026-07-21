from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_claim_extraction import (
    extract_project_claims,
    load_claim_candidates,
)

from .fusion import fuse_claim_candidates
from .models import (
    FusionStatus,
    KnowledgeCluster,
    KnowledgeFusionResult,
    ValueVariant,
)


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def save_fusion_result(result: KnowledgeFusionResult, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(result), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_fusion_result(path: Path) -> KnowledgeFusionResult:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    clusters = tuple(
        KnowledgeCluster(
            id=item["id"],
            semantic_key=item["semantic_key"],
            subject=item["subject"],
            predicate=item["predicate"],
            unit=item.get("unit"),
            candidate_ids=tuple(item["candidate_ids"]),
            document_ids=tuple(item["document_ids"]),
            variants=tuple(
                ValueVariant(
                    normalized_value=variant["normalized_value"],
                    unit=variant.get("unit"),
                    candidate_ids=tuple(variant["candidate_ids"]),
                    document_ids=tuple(variant["document_ids"]),
                    confidence_max=float(variant["confidence_max"]),
                    confidence_mean=float(variant["confidence_mean"]),
                )
                for variant in item["variants"]
            ),
            status=FusionStatus(item["status"]),
            support_count=int(item["support_count"]),
            fingerprint=item["fingerprint"],
        )
        for item in raw.get("clusters", [])
    )
    return KnowledgeFusionResult(project_id=raw["project_id"], clusters=clusters)


class FusionSummary(TypedDict):
    project_id: str
    clusters: int
    singleton: int
    consistent: int
    conflicting: int
    value_variants: int
    by_status: dict[str, int]


def summarize_fusion(result: KnowledgeFusionResult) -> FusionSummary:
    return {
        "project_id": result.project_id,
        "clusters": len(result.clusters),
        "singleton": result.singleton_count,
        "consistent": result.consistent_count,
        "conflicting": result.conflicting_count,
        "value_variants": sum(len(cluster.variants) for cluster in result.clusters),
        "by_status": dict(
            sorted(Counter(cluster.status.value for cluster in result.clusters).items())
        ),
    }


def fuse_project(project_file: Path) -> tuple[KnowledgeFusionResult, Path]:
    claim_file = project_file.with_name("crow-claim-candidates.json")
    if claim_file.exists():
        claims = load_claim_candidates(claim_file)
    else:
        claims, _ = extract_project_claims(project_file)

    result = fuse_claim_candidates(claims)
    output = project_file.with_name("crow-knowledge-fusion.json")
    save_fusion_result(result, output)
    return result, output
