from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_commercial_adjustment import load_adjusted

from .models import (
    CommercialReview,
    CommercialReviewEvent,
    CommercialReviewStatus,
)
from .workflow import initialize_commercial_review, transition_commercial_review


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def save_review(review: CommercialReview, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(review), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_review(path: Path) -> CommercialReview:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return CommercialReview(
        project_id=raw["project_id"],
        baseline_id=raw["baseline_id"],
        adjustment_profile_id=raw["adjustment_profile_id"],
        source_price_book_id=raw["source_price_book_id"],
        currency=raw["currency"],
        grand_total=float(raw["grand_total"]),
        unresolved_count=int(raw["unresolved_count"]),
        status=CommercialReviewStatus(raw["status"]),
        latest_event_id=raw.get("latest_event_id"),
        history=tuple(
            CommercialReviewEvent(
                id=item["id"],
                previous_status=CommercialReviewStatus(item["previous_status"]),
                new_status=CommercialReviewStatus(item["new_status"]),
                reviewer=item["reviewer"],
                reason=item["reason"],
                created_at=datetime.fromisoformat(item["created_at"]),
                supersedes_event_id=item.get("supersedes_event_id"),
                fingerprint=item["fingerprint"],
            )
            for item in raw.get("history", [])
        ),
    )


class CommercialReviewSummary(TypedDict):
    project_id: str
    status: str
    currency: str
    grand_total: float
    unresolved: int
    events: int
    approved: bool


def summarize_review(review: CommercialReview) -> CommercialReviewSummary:
    return {
        "project_id": review.project_id,
        "status": review.status.value,
        "currency": review.currency,
        "grand_total": review.grand_total,
        "unresolved": review.unresolved_count,
        "events": len(review.history),
        "approved": review.is_approved,
    }


def initialize_project_commercial_review(
    project_file: Path,
    adjusted_file: Path | None = None,
) -> tuple[CommercialReview, Path]:
    source = adjusted_file or project_file.with_name("crow-commercial-adjustments.json")
    adjusted = load_adjusted(source)
    review = initialize_commercial_review(adjusted)
    output = project_file.with_name("crow-commercial-review.json")
    save_review(review, output)
    return review, output


def update_project_commercial_review(
    project_file: Path,
    new_status: CommercialReviewStatus,
    reviewer: str,
    reason: str,
    created_at: datetime,
    review_file: Path | None = None,
) -> tuple[CommercialReview, Path]:
    source = review_file or project_file.with_name("crow-commercial-review.json")
    review = load_review(source)
    updated = transition_commercial_review(
        review,
        new_status,
        reviewer,
        reason,
        created_at,
    )
    save_review(updated, source)
    return updated, source
