from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_document_intelligence import DocumentIndex, load_index

from .extractors import extract_observations
from .models import (
    Observation,
    ObservationCollection,
    ObservationEvidence,
    ObservationSource,
    ObservationType,
    SourceLocator,
)


def observe_index(index: DocumentIndex) -> ObservationCollection:
    page_by_id = {page.id: page for page in index.pages}
    observations: list[Observation] = []
    for region in index.regions:
        page = page_by_id.get(region.page_id)
        if page is None or not region.text:
            continue
        observations.extend(extract_observations(page, region))
    unique_by_id = {observation.id: observation for observation in observations}
    return ObservationCollection(
        project_id=index.project_id,
        observations=tuple(unique_by_id.values()),
    )


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def save_collection(collection: ObservationCollection, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(collection), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_collection(path: Path) -> ObservationCollection:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    observations: list[Observation] = []
    for item in raw.get("observations", []):
        evidence_raw = item["evidence"]
        locator_raw = evidence_raw["locator"]
        observations.append(
            Observation(
                id=item["id"],
                observation_type=ObservationType(item["observation_type"]),
                value=item["value"],
                normalized_value=item["normalized_value"],
                content_sha256=item["content_sha256"],
                evidence=ObservationEvidence(
                    source=ObservationSource(evidence_raw["source"]),
                    source_text=evidence_raw["source_text"],
                    confidence=evidence_raw["confidence"],
                    locator=SourceLocator(**locator_raw),
                    page_sha256=evidence_raw["page_sha256"],
                ),
            )
        )
    return ObservationCollection(
        project_id=raw["project_id"],
        observations=tuple(observations),
    )


class ObservationSummary(TypedDict):
    project_id: str
    observations: int
    unique_content: int
    duplicates: int
    by_type: dict[str, int]


def summarize_observations(collection: ObservationCollection) -> ObservationSummary:
    return {
        "project_id": collection.project_id,
        "observations": len(collection.observations),
        "unique_content": collection.unique_content_count,
        "duplicates": collection.duplicate_count,
        "by_type": dict(
            sorted(
                Counter(
                    observation.observation_type.value for observation in collection.observations
                ).items()
            )
        ),
    }


def observe_project(project_file: Path) -> tuple[ObservationCollection, Path]:
    index = load_index(project_file)
    collection = observe_index(index)
    output = project_file.with_name("crow-observations.json")
    save_collection(collection, output)
    return collection, output
