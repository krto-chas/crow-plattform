from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_decision_engine import load_decision_result
from crow_technical_review import load_review_set

from .compare import compare_approved_decisions
from .models import (
    BaselineItem,
    ChangeDirection,
    DeltaType,
    TechnicalBaseline,
    TechnicalDelta,
    TechnicalDeltaProvenance,
    TechnicalDeltaSet,
    ValueKind,
)


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def load_baseline(path: Path) -> TechnicalBaseline:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return TechnicalBaseline(
        project_id=raw["project_id"],
        baseline_id=raw["baseline_id"],
        name=raw["name"],
        items=tuple(
            BaselineItem(
                id=item["id"],
                comparison_key=item["comparison_key"],
                category=item["category"],
                title=item["title"],
                value=item["value"],
                unit=item.get("unit"),
                source=item.get("source", "baseline"),
                object_ref=item.get("object_ref"),
                property_name=item.get("property_name"),
                value_kind=ValueKind(item.get("value_kind", "text")),
                quantity=(float(item["quantity"]) if item.get("quantity") is not None else None),
            )
            for item in raw.get("items", [])
        ),
    )


def write_baseline_template(path: Path, project_id: str = "project-id") -> None:
    payload = {
        "project_id": project_id,
        "baseline_id": "baseline.contract",
        "name": "Contract technical baseline",
        "items": [
            {
                "id": "baseline:ventilation:velocity",
                "comparison_key": "ventilation|calculated air velocity exceeds limit",
                "category": "ventilation",
                "title": "Calculated air velocity exceeds limit",
                "value": "Accepted airflow and duct area are within the original design limit.",
                "unit": None,
                "source": "Contract baseline",
                "object_ref": "AHU-03",
                "property_name": "air_velocity",
                "value_kind": "number",
                "quantity": 5.0,
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_delta_set(delta_set: TechnicalDeltaSet, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(delta_set), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_delta_set(path: Path) -> TechnicalDeltaSet:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return TechnicalDeltaSet(
        project_id=raw["project_id"],
        baseline_id=raw["baseline_id"],
        deltas=tuple(
            TechnicalDelta(
                id=item["id"],
                comparison_key=item["comparison_key"],
                delta_type=DeltaType(item["delta_type"]),
                category=item["category"],
                title=item["title"],
                baseline_value=item.get("baseline_value"),
                approved_value=item.get("approved_value"),
                unit=item.get("unit"),
                confidence=(
                    float(item["confidence"]) if item.get("confidence") is not None else None
                ),
                provenance=TechnicalDeltaProvenance(
                    baseline_item_id=item["provenance"].get("baseline_item_id"),
                    decision_id=item["provenance"].get("decision_id"),
                    review_event_id=item["provenance"].get("review_event_id"),
                    accepted_claim_ids=tuple(item["provenance"].get("accepted_claim_ids", [])),
                    authority_decision_ids=tuple(
                        item["provenance"].get("authority_decision_ids", [])
                    ),
                    document_ids=tuple(item["provenance"].get("document_ids", [])),
                    trace=tuple(item["provenance"].get("trace", [])),
                ),
                fingerprint=item["fingerprint"],
                object_ref=item.get("object_ref"),
                property_name=item.get("property_name"),
                value_kind=ValueKind(item.get("value_kind", "text")),
                baseline_quantity=(
                    float(item["baseline_quantity"])
                    if item.get("baseline_quantity") is not None
                    else None
                ),
                approved_quantity=(
                    float(item["approved_quantity"])
                    if item.get("approved_quantity") is not None
                    else None
                ),
                quantity_delta=(
                    float(item["quantity_delta"])
                    if item.get("quantity_delta") is not None
                    else None
                ),
                change_direction=ChangeDirection(item.get("change_direction", "changed")),
            )
            for item in raw.get("deltas", [])
        ),
    )


class DeltaSummary(TypedDict):
    project_id: str
    baseline_id: str
    total: int
    changed: int
    by_type: dict[str, int]


def summarize_deltas(delta_set: TechnicalDeltaSet) -> DeltaSummary:
    by_type: dict[str, int] = {}
    for delta in delta_set.deltas:
        by_type[delta.delta_type.value] = by_type.get(delta.delta_type.value, 0) + 1
    return {
        "project_id": delta_set.project_id,
        "baseline_id": delta_set.baseline_id,
        "total": len(delta_set.deltas),
        "changed": delta_set.changed_count,
        "by_type": dict(sorted(by_type.items())),
    }


def build_project_deltas(
    project_file: Path,
    baseline_file: Path,
    decisions_file: Path | None = None,
    reviews_file: Path | None = None,
) -> tuple[TechnicalDeltaSet, Path]:
    decisions_path = decisions_file or project_file.with_name("crow-technical-decisions.json")
    reviews_path = reviews_file or project_file.with_name("crow-technical-reviews.json")
    baseline = load_baseline(baseline_file)
    decisions = load_decision_result(decisions_path)
    reviews = load_review_set(reviews_path)
    delta_set = compare_approved_decisions(baseline, decisions, reviews)
    output = project_file.with_name("crow-technical-deltas.json")
    save_delta_set(delta_set, output)
    return delta_set, output
