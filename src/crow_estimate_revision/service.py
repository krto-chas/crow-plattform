from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_estimate_structure import load_structured_estimate

from .engine import compare_estimates
from .models import (
    EstimateChangeType,
    EstimateFieldChange,
    EstimateLineChange,
    EstimateRevision,
)


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def save_revision(revision: EstimateRevision, path: Path) -> None:
    path.write_text(
        json.dumps(
            asdict(revision),
            default=_default,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def load_revision(path: Path) -> EstimateRevision:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return EstimateRevision(
        id=raw["id"],
        project_id=raw["project_id"],
        baseline_id=raw["baseline_id"],
        previous_estimate_id=raw["previous_estimate_id"],
        current_estimate_id=raw["current_estimate_id"],
        previous_structure_id=raw["previous_structure_id"],
        current_structure_id=raw["current_structure_id"],
        previous_fingerprint=raw["previous_fingerprint"],
        current_fingerprint=raw["current_fingerprint"],
        currency=raw["currency"],
        line_changes=tuple(
            EstimateLineChange(
                id=item["id"],
                change_type=EstimateChangeType(item["change_type"]),
                estimate_line_id=item["estimate_line_id"],
                previous_position=item.get("previous_position"),
                current_position=item.get("current_position"),
                previous_fingerprint=item.get("previous_fingerprint"),
                current_fingerprint=item.get("current_fingerprint"),
                field_changes=tuple(
                    EstimateFieldChange(
                        field=change["field"],
                        previous=change.get("previous"),
                        current=change.get("current"),
                    )
                    for change in item.get("field_changes", [])
                ),
                explanation=item["explanation"],
                amount_delta=float(item["amount_delta"]),
                fingerprint=item["fingerprint"],
            )
            for item in raw.get("line_changes", [])
        ),
        previous_total=float(raw["previous_total"]),
        current_total=float(raw["current_total"]),
        total_delta=float(raw["total_delta"]),
        fingerprint=raw["fingerprint"],
    )


class EstimateRevisionSummary(TypedDict):
    revision_id: str
    previous_estimate_id: str
    current_estimate_id: str
    currency: str
    added: int
    removed: int
    modified: int
    unchanged: int
    previous_total: float
    current_total: float
    total_delta: float


def summarize_revision(revision: EstimateRevision) -> EstimateRevisionSummary:
    return {
        "revision_id": revision.id,
        "previous_estimate_id": revision.previous_estimate_id,
        "current_estimate_id": revision.current_estimate_id,
        "currency": revision.currency,
        "added": revision.added_count,
        "removed": revision.removed_count,
        "modified": revision.modified_count,
        "unchanged": revision.unchanged_count,
        "previous_total": revision.previous_total,
        "current_total": revision.current_total,
        "total_delta": revision.total_delta,
    }


def build_project_revision(
    project_file: Path,
    revision_id: str,
    previous_file: Path,
    current_file: Path,
    *,
    include_unchanged: bool = False,
) -> tuple[EstimateRevision, Path]:
    revision = compare_estimates(
        load_structured_estimate(previous_file),
        load_structured_estimate(current_file),
        revision_id,
        include_unchanged=include_unchanged,
    )
    output = project_file.with_name("crow-estimate-revision.json")
    save_revision(revision, output)
    return revision, output
