from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_decision_engine import load_decision_result
from crow_technical_validation import load_result as load_validation_result

from .models import (
    ReviewEvent,
    ReviewRecord,
    ReviewStatus,
    ReviewTargetType,
    TechnicalReviewSet,
)
from .workflow import initialize_review_set, transition_record


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def save_review_set(review_set: TechnicalReviewSet, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(review_set), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_review_set(path: Path) -> TechnicalReviewSet:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    records = tuple(
        ReviewRecord(
            target_id=item["target_id"],
            target_type=ReviewTargetType(item["target_type"]),
            status=ReviewStatus(item["status"]),
            latest_event_id=item.get("latest_event_id"),
            history=tuple(
                ReviewEvent(
                    id=event["id"],
                    target_id=event["target_id"],
                    target_type=ReviewTargetType(event["target_type"]),
                    previous_status=ReviewStatus(event["previous_status"]),
                    new_status=ReviewStatus(event["new_status"]),
                    reviewer=event["reviewer"],
                    reason=event["reason"],
                    created_at=datetime.fromisoformat(event["created_at"]),
                    supersedes_event_id=event.get("supersedes_event_id"),
                    fingerprint=event["fingerprint"],
                )
                for event in item.get("history", [])
            ),
        )
        for item in raw.get("records", [])
    )
    return TechnicalReviewSet(project_id=raw["project_id"], records=records)


class ReviewSummary(TypedDict):
    project_id: str
    records: int
    by_status: dict[str, int]
    by_target_type: dict[str, int]


def summarize_reviews(review_set: TechnicalReviewSet) -> ReviewSummary:
    by_status: dict[str, int] = {}
    by_target_type: dict[str, int] = {}
    for record in review_set.records:
        by_status[record.status.value] = by_status.get(record.status.value, 0) + 1
        target_type = record.target_type.value
        by_target_type[target_type] = by_target_type.get(target_type, 0) + 1
    return {
        "project_id": review_set.project_id,
        "records": len(review_set.records),
        "by_status": dict(sorted(by_status.items())),
        "by_target_type": dict(sorted(by_target_type.items())),
    }


def initialize_project_reviews(
    project_file: Path,
    decisions_file: Path | None = None,
    validation_file: Path | None = None,
) -> tuple[TechnicalReviewSet, Path]:
    decisions_path = decisions_file or project_file.with_name("crow-technical-decisions.json")
    validation_path = validation_file or project_file.with_name("crow-technical-validation.json")
    decisions = load_decision_result(decisions_path)
    validation = load_validation_result(validation_path)
    review_set = initialize_review_set(decisions, validation)
    output = project_file.with_name("crow-technical-reviews.json")
    save_review_set(review_set, output)
    return review_set, output


def update_project_review(
    project_file: Path,
    target_id: str,
    new_status: ReviewStatus,
    reviewer: str,
    reason: str,
    review_file: Path | None = None,
) -> tuple[TechnicalReviewSet, Path]:
    output = review_file or project_file.with_name("crow-technical-reviews.json")
    review_set = load_review_set(output)
    updated = transition_record(review_set, target_id, new_status, reviewer, reason)
    save_review_set(updated, output)
    return updated, output
