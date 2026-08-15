from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
from typing import Any

from .models import GeometryDocument
from .observations import discover_system_observations


def _normalise(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _group_id(system_id: str, observation_type: str, value: str) -> str:
    digest = sha256(f"{system_id}:{observation_type}:{value}".encode()).hexdigest()[:16]
    return f"candidate-group-{digest}"


def consolidate_observations(
    document: GeometryDocument,
    *,
    tolerance: float = 0.001,
    association_radius: float = 100.0,
    layers: Iterable[str] | None = None,
    visible_only: bool = False,
) -> dict[str, Any]:
    source = discover_system_observations(
        document,
        tolerance=tolerance,
        association_radius=association_radius,
        layers=layers,
        visible_only=visible_only,
    )
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in source["observations"]:
        observation = dict(item)
        key = (
            str(observation["system_id"]),
            str(observation["observation_type"]),
            _normalise(observation.get("candidate_value")),
        )
        grouped.setdefault(key, []).append(observation)

    candidates: list[dict[str, Any]] = []
    by_system_type: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for (system_id, observation_type, value), items in grouped.items():
        confidences = [float(item["confidence"]) for item in items]
        score = round(sum(confidences) / len(confidences), 4)
        candidate = {
            "candidate_group_id": _group_id(system_id, observation_type, value),
            "system_id": system_id,
            "observation_type": observation_type,
            "normalized_value": value,
            "display_value": str(items[0].get("candidate_value") or ""),
            "evidence_count": len(items),
            "observation_ids": sorted(str(item["observation_id"]) for item in items),
            "candidate_object_ids": sorted(str(item["candidate_object_id"]) for item in items),
            "score": score,
            "max_confidence": round(max(confidences), 4),
            "min_distance": min(float(item["distance"]) for item in items),
            "status": "candidate",
            "domain_semantics": False,
            "conflict": False,
            "rank": 0,
        }
        candidates.append(candidate)
        by_system_type.setdefault((system_id, observation_type), []).append(candidate)

    conflict_count = 0
    for bucket in by_system_type.values():
        bucket.sort(
            key=lambda item: (
                -float(item["score"]),
                -int(item["evidence_count"]),
                str(item["normalized_value"]),
            )
        )
        conflict = len(bucket) > 1
        if conflict:
            conflict_count += 1
        for rank, item in enumerate(bucket, start=1):
            item["rank"] = rank
            item["conflict"] = conflict
            item["review_status"] = "needs_review" if conflict else "ready_for_domain_review"

    candidates.sort(
        key=lambda item: (str(item["system_id"]), str(item["observation_type"]), int(item["rank"]))
    )
    return {
        "consolidation_version": "crow-geometry-consolidation-v1",
        "domain_semantics": False,
        "candidate_group_count": len(candidates),
        "conflict_set_count": conflict_count,
        "source_observation_count": source["observation_count"],
        "candidates": candidates,
    }
