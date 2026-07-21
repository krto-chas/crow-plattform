from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_scope_impact import load_scope_impacts

from .engine import derive_commercial_impacts
from .models import (
    CommercialImpact,
    CommercialImpactProvenance,
    CommercialImpactSet,
    CostType,
    PriceBook,
    PricingStatus,
    UnitRate,
)


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def load_price_book(path: Path) -> PriceBook:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    currency = raw.get("currency", "SEK")
    return PriceBook(
        id=raw["id"],
        name=raw["name"],
        version=raw.get("version", "1.0.0"),
        currency=currency,
        rates=tuple(
            UnitRate(
                id=item["id"],
                category=item["category"],
                property_name=item.get("property_name"),
                impact_types=tuple(item.get("impact_types", [])),
                cost_type=CostType(item["cost_type"]),
                unit=item["unit"],
                currency=item.get("currency", currency),
                unit_rate=float(item["unit_rate"]),
                description=item.get("description", item["id"]),
                enabled=bool(item.get("enabled", True)),
                priority=int(item.get("priority", 0)),
                version=item.get("version", "1.0.0"),
            )
            for item in raw.get("rates", [])
        ),
    )


def write_price_book_template(path: Path) -> None:
    payload = {
        "id": "crow.pricebook.ventilation.example",
        "name": "Ventilation example price book",
        "version": "1.0.0",
        "currency": "SEK",
        "rates": [
            {
                "id": "ventilation.air-velocity.adjustment",
                "category": "ventilation",
                "property_name": "air_velocity",
                "impact_types": ["changed_work"],
                "cost_type": "labour",
                "unit": "M/S",
                "currency": "SEK",
                "unit_rate": 1250.0,
                "description": "Engineering and adjustment for air-velocity change",
                "priority": 100,
                "version": "1.0.0",
            }
        ],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_commercial_impacts(result: CommercialImpactSet, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(result), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_commercial_impacts(path: Path) -> CommercialImpactSet:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return CommercialImpactSet(
        project_id=raw["project_id"],
        baseline_id=raw["baseline_id"],
        price_book_id=raw["price_book_id"],
        currency=raw["currency"],
        impacts=tuple(
            CommercialImpact(
                id=item["id"],
                scope_impact_id=item["scope_impact_id"],
                cost_type=(
                    CostType(item["cost_type"]) if item.get("cost_type") is not None else None
                ),
                description=item["description"],
                quantity=(float(item["quantity"]) if item.get("quantity") is not None else None),
                unit=item.get("unit"),
                unit_rate=(float(item["unit_rate"]) if item.get("unit_rate") is not None else None),
                currency=item["currency"],
                amount=(float(item["amount"]) if item.get("amount") is not None else None),
                pricing_status=PricingStatus(item["pricing_status"]),
                requires_review=bool(item["requires_review"]),
                confidence=(
                    float(item["confidence"]) if item.get("confidence") is not None else None
                ),
                provenance=CommercialImpactProvenance(
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
                    trace=tuple(item["provenance"].get("trace", [])),
                ),
                fingerprint=item["fingerprint"],
            )
            for item in raw.get("impacts", [])
        ),
    )


class CommercialSummary(TypedDict):
    project_id: str
    baseline_id: str
    currency: str
    total: float
    items: int
    unresolved: int
    by_status: dict[str, int]
    by_cost_type: dict[str, float]


def summarize_commercial_impacts(result: CommercialImpactSet) -> CommercialSummary:
    by_status: dict[str, int] = {}
    by_cost_type: dict[str, float] = {}
    for impact in result.impacts:
        by_status[impact.pricing_status.value] = by_status.get(impact.pricing_status.value, 0) + 1
        if impact.cost_type is not None and impact.amount is not None:
            key = impact.cost_type.value
            by_cost_type[key] = by_cost_type.get(key, 0.0) + impact.amount
    return {
        "project_id": result.project_id,
        "baseline_id": result.baseline_id,
        "currency": result.currency,
        "total": result.priced_total,
        "items": len(result.impacts),
        "unresolved": result.unresolved_count,
        "by_status": dict(sorted(by_status.items())),
        "by_cost_type": dict(sorted(by_cost_type.items())),
    }


def build_project_commercial_impacts(
    project_file: Path,
    price_book_file: Path,
    scope_file: Path | None = None,
) -> tuple[CommercialImpactSet, Path]:
    scope_path = scope_file or project_file.with_name("crow-scope-impacts.json")
    scope_impacts = load_scope_impacts(scope_path)
    price_book = load_price_book(price_book_file)
    result = derive_commercial_impacts(scope_impacts, price_book)
    output = project_file.with_name("crow-commercial-impacts.json")
    save_commercial_impacts(result, output)
    return result, output
