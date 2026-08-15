from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_commercial_adjustment import load_adjusted
from crow_commercial_impact import load_commercial_impacts
from crow_commercial_review import load_review

from .generator import generate_estimate
from .models import (
    Estimate,
    EstimateLine,
    EstimateLineProvenance,
    EstimateLineStatus,
)


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def save_estimate(estimate: Estimate, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(estimate), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_estimate(path: Path) -> Estimate:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return Estimate(
        project_id=raw["project_id"],
        baseline_id=raw["baseline_id"],
        estimate_id=raw["estimate_id"],
        currency=raw["currency"],
        price_book_id=raw["price_book_id"],
        adjustment_profile_id=raw["adjustment_profile_id"],
        commercial_review_event_id=raw["commercial_review_event_id"],
        lines=tuple(
            EstimateLine(
                id=item["id"],
                line_number=int(item["line_number"]),
                status=EstimateLineStatus(item["status"]),
                description=item["description"],
                cost_type=item.get("cost_type"),
                quantity=float(item["quantity"]),
                unit=item["unit"],
                unit_rate=float(item["unit_rate"]),
                net_amount=float(item["net_amount"]),
                adjustment_amount=float(item["adjustment_amount"]),
                total_amount=float(item["total_amount"]),
                currency=item["currency"],
                provenance=EstimateLineProvenance(
                    commercial_impact_id=item["provenance"]["commercial_impact_id"],
                    scope_impact_id=item["provenance"]["scope_impact_id"],
                    technical_delta_id=item["provenance"]["technical_delta_id"],
                    decision_id=item["provenance"].get("decision_id"),
                    review_event_id=item["provenance"].get("review_event_id"),
                    accepted_claim_ids=tuple(item["provenance"].get("accepted_claim_ids", [])),
                    authority_decision_ids=tuple(
                        item["provenance"].get("authority_decision_ids", [])
                    ),
                    document_ids=tuple(item["provenance"].get("document_ids", [])),
                    scope_rule_id=item["provenance"].get("scope_rule_id"),
                    price_book_id=item["provenance"]["price_book_id"],
                    unit_rate_id=item["provenance"].get("unit_rate_id"),
                    adjustment_profile_id=item["provenance"]["adjustment_profile_id"],
                    commercial_review_event_id=(item["provenance"]["commercial_review_event_id"]),
                    adjustment_ids=tuple(item["provenance"].get("adjustment_ids", [])),
                    trace=tuple(item["provenance"].get("trace", [])),
                ),
                fingerprint=item["fingerprint"],
            )
            for item in raw.get("lines", [])
        ),
    )


class EstimateSummary(TypedDict):
    project_id: str
    estimate_id: str
    currency: str
    lines: int
    net_total: float
    adjustment_total: float
    grand_total: float


def summarize_estimate(estimate: Estimate) -> EstimateSummary:
    return {
        "project_id": estimate.project_id,
        "estimate_id": estimate.estimate_id,
        "currency": estimate.currency,
        "lines": len(estimate.lines),
        "net_total": estimate.net_total,
        "adjustment_total": estimate.adjustment_total,
        "grand_total": estimate.grand_total,
    }


def build_project_estimate(
    project_file: Path,
    estimate_id: str,
    commercial_file: Path | None = None,
    adjusted_file: Path | None = None,
    review_file: Path | None = None,
) -> tuple[Estimate, Path]:
    commercial_path = commercial_file or project_file.with_name("crow-commercial-impacts.json")
    adjusted_path = adjusted_file or project_file.with_name("crow-commercial-adjustments.json")
    review_path = review_file or project_file.with_name("crow-commercial-review.json")
    estimate = generate_estimate(
        load_commercial_impacts(commercial_path),
        load_adjusted(adjusted_path),
        load_review(review_path),
        estimate_id,
    )
    output = project_file.with_name("crow-estimate.json")
    save_estimate(estimate, output)
    return estimate, output
