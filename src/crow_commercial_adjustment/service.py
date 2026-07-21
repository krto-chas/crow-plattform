from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_commercial_impact import load_commercial_impacts

from .engine import apply_adjustments
from .models import (
    AdjustedCommercialImpact,
    AdjustedCommercialImpactSet,
    AdjustmentBase,
    AdjustmentKind,
    AdjustmentType,
    AppliedAdjustment,
    CommercialAdjustmentProfile,
    CommercialAdjustmentRule,
)


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def load_profile(path: Path) -> CommercialAdjustmentProfile:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return CommercialAdjustmentProfile(
        id=raw["id"],
        name=raw["name"],
        version=raw.get("version", "1.0.0"),
        currency=raw.get("currency", "SEK"),
        rules=tuple(
            CommercialAdjustmentRule(
                id=item["id"],
                name=item["name"],
                kind=AdjustmentKind(item["kind"]),
                adjustment_type=AdjustmentType(item["adjustment_type"]),
                base=AdjustmentBase(item.get("base", "net_amount")),
                value=float(item["value"]),
                categories=tuple(item.get("categories", [])),
                cost_types=tuple(item.get("cost_types", [])),
                enabled=bool(item.get("enabled", True)),
                priority=int(item.get("priority", 0)),
                version=item.get("version", "1.0.0"),
            )
            for item in raw.get("rules", [])
        ),
    )


def write_profile_template(path: Path) -> None:
    payload = {
        "id": "crow.adjustments.example",
        "name": "Example commercial adjustments",
        "version": "1.0.0",
        "currency": "SEK",
        "rules": [
            {
                "id": "markup.overhead",
                "name": "Overhead markup",
                "kind": "markup",
                "adjustment_type": "percentage",
                "base": "net_amount",
                "value": 8.0,
                "cost_types": ["labour", "material", "equipment", "subcontract"],
                "priority": 100,
            },
            {
                "id": "risk.contingency",
                "name": "Risk contingency",
                "kind": "risk",
                "adjustment_type": "percentage",
                "base": "running_total",
                "value": 5.0,
                "priority": 200,
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_adjusted(result: AdjustedCommercialImpactSet, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(result), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_adjusted(path: Path) -> AdjustedCommercialImpactSet:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return AdjustedCommercialImpactSet(
        project_id=raw["project_id"],
        baseline_id=raw["baseline_id"],
        source_price_book_id=raw["source_price_book_id"],
        adjustment_profile_id=raw["adjustment_profile_id"],
        currency=raw["currency"],
        unresolved_count=int(raw.get("unresolved_count", 0)),
        impacts=tuple(
            AdjustedCommercialImpact(
                commercial_impact_id=item["commercial_impact_id"],
                description=item["description"],
                category=item.get("category"),
                cost_type=item.get("cost_type"),
                net_amount=float(item["net_amount"]),
                adjustments=tuple(
                    AppliedAdjustment(
                        id=adj["id"],
                        rule_id=adj["rule_id"],
                        kind=AdjustmentKind(adj["kind"]),
                        description=adj["description"],
                        base_amount=float(adj["base_amount"]),
                        rate=float(adj["rate"]) if adj.get("rate") is not None else None,
                        amount=float(adj["amount"]),
                        currency=adj["currency"],
                        fingerprint=adj["fingerprint"],
                    )
                    for adj in item.get("adjustments", [])
                ),
                adjusted_total=float(item["adjusted_total"]),
                currency=item["currency"],
            )
            for item in raw.get("impacts", [])
        ),
    )


class AdjustmentSummary(TypedDict):
    project_id: str
    currency: str
    net_total: float
    adjustment_total: float
    grand_total: float
    adjusted_items: int
    unresolved: int
    by_kind: dict[str, float]


def summarize_adjustments(result: AdjustedCommercialImpactSet) -> AdjustmentSummary:
    by_kind: dict[str, float] = {}
    for item in result.impacts:
        for adjustment in item.adjustments:
            key = adjustment.kind.value
            by_kind[key] = by_kind.get(key, 0.0) + adjustment.amount
    return {
        "project_id": result.project_id,
        "currency": result.currency,
        "net_total": result.net_total,
        "adjustment_total": result.adjustment_total,
        "grand_total": result.grand_total,
        "adjusted_items": len(result.impacts),
        "unresolved": result.unresolved_count,
        "by_kind": dict(sorted(by_kind.items())),
    }


def apply_project_adjustments(
    project_file: Path,
    profile_file: Path,
    commercial_file: Path | None = None,
) -> tuple[AdjustedCommercialImpactSet, Path]:
    source = commercial_file or project_file.with_name("crow-commercial-impacts.json")
    commercial = load_commercial_impacts(source)
    profile = load_profile(profile_file)
    result = apply_adjustments(commercial, profile)
    output = project_file.with_name("crow-commercial-adjustments.json")
    save_adjusted(result, output)
    return result, output
