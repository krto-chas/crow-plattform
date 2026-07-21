from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_observation_engine import (
    ObservationCollection,
    load_collection,
    observe_project,
)

from .extractor import extract_claim_candidates
from .models import (
    ClaimCandidate,
    ClaimCandidateCollection,
    ClaimCandidateStatus,
    ClaimCandidateType,
    ClaimProvenance,
)


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def save_claim_candidates(
    collection: ClaimCandidateCollection,
    path: Path,
) -> None:
    path.write_text(
        json.dumps(asdict(collection), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_claim_candidates(path: Path) -> ClaimCandidateCollection:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    candidates = tuple(
        ClaimCandidate(
            id=item["id"],
            candidate_type=ClaimCandidateType(item["candidate_type"]),
            subject=item["subject"],
            predicate=item["predicate"],
            value=item["value"],
            normalized_value=item["normalized_value"],
            unit=item.get("unit"),
            confidence=float(item["confidence"]),
            status=ClaimCandidateStatus(item["status"]),
            provenance=ClaimProvenance(
                observation_ids=tuple(item["provenance"]["observation_ids"]),
                document_id=item["provenance"]["document_id"],
                page_number=int(item["provenance"]["page_number"]),
                region_id=item["provenance"]["region_id"],
                locator_values=tuple(item["provenance"]["locator_values"]),
            ),
            fingerprint=item["fingerprint"],
        )
        for item in raw.get("candidates", [])
    )
    return ClaimCandidateCollection(
        project_id=raw["project_id"],
        candidates=candidates,
    )


class ClaimCandidateSummary(TypedDict):
    project_id: str
    candidates: int
    unique_candidates: int
    duplicates: int
    by_type: dict[str, int]
    average_confidence: float


def summarize_claim_candidates(
    collection: ClaimCandidateCollection,
) -> ClaimCandidateSummary:
    count = len(collection.candidates)
    average = (
        sum(candidate.confidence for candidate in collection.candidates) / count if count else 0.0
    )
    return {
        "project_id": collection.project_id,
        "candidates": count,
        "unique_candidates": collection.unique_count,
        "duplicates": collection.duplicate_count,
        "by_type": dict(
            sorted(
                Counter(
                    candidate.candidate_type.value for candidate in collection.candidates
                ).items()
            )
        ),
        "average_confidence": round(average, 4),
    }


def _load_or_create_observations(project_file: Path) -> ObservationCollection:
    observation_file = project_file.with_name("crow-observations.json")
    if observation_file.exists():
        return load_collection(observation_file)
    collection, _ = observe_project(project_file)
    return collection


def extract_project_claims(
    project_file: Path,
) -> tuple[ClaimCandidateCollection, Path]:
    observations = _load_or_create_observations(project_file)
    candidates = extract_claim_candidates(observations)
    output = project_file.with_name("crow-claim-candidates.json")
    save_claim_candidates(candidates, output)
    return candidates, output
