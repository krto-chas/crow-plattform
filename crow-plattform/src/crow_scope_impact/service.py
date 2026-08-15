from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from crow_technical_delta import load_delta_set

from .engine import derive_scope_impacts
from .models import (
    QuantityBasis,
    ScopeImpact,
    ScopeImpactProvenance,
    ScopeImpactRule,
    ScopeImpactRuleSet,
    ScopeImpactSet,
    ScopeImpactType,
)


def _default(value: object) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def load_rule_set(path: Path) -> ScopeImpactRuleSet:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return ScopeImpactRuleSet(
        id=raw["id"],
        name=raw["name"],
        version=raw.get("version", "1.0.0"),
        rules=tuple(
            ScopeImpactRule(
                id=item["id"],
                name=item["name"],
                categories=tuple(item.get("categories", [])),
                property_names=tuple(item.get("property_names", [])),
                change_directions=tuple(item.get("change_directions", [])),
                impact_type=ScopeImpactType(item["impact_type"]),
                quantity_basis=QuantityBasis(item["quantity_basis"]),
                output_unit=item.get("output_unit"),
                multiplier=float(item.get("multiplier", 1.0)),
                fixed_quantity=(
                    float(item["fixed_quantity"])
                    if item.get("fixed_quantity") is not None
                    else None
                ),
                description_template=item.get("description_template", "{title}"),
                enabled=bool(item.get("enabled", True)),
                priority=int(item.get("priority", 0)),
                version=item.get("version", "1.0.0"),
            )
            for item in raw.get("rules", [])
        ),
    )


def write_rule_set_template(path: Path) -> None:
    payload = {
        "id": "crow.scope.ventilation.example",
        "name": "Ventilation scope-impact rules",
        "version": "1.0.0",
        "rules": [
            {
                "id": "ventilation.air-velocity.changed",
                "name": "Air velocity change affects duct scope",
                "categories": ["ventilation"],
                "property_names": ["air_velocity"],
                "change_directions": ["increase", "decrease"],
                "impact_type": "changed_work",
                "quantity_basis": "delta_quantity",
                "output_unit": "M/S",
                "multiplier": 1.0,
                "description_template": (
                    "{object_ref}: {property_name} changed from "
                    "{baseline_value} to {approved_value} {unit}"
                ),
                "priority": 100,
                "version": "1.0.0",
            }
        ],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_scope_impacts(result: ScopeImpactSet, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(result), default=_default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_scope_impacts(path: Path) -> ScopeImpactSet:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return ScopeImpactSet(
        project_id=raw["project_id"],
        baseline_id=raw["baseline_id"],
        rule_set_id=raw["rule_set_id"],
        impacts=tuple(
            ScopeImpact(
                id=item["id"],
                impact_type=ScopeImpactType(item["impact_type"]),
                category=item["category"],
                object_ref=item.get("object_ref"),
                property_name=item.get("property_name"),
                description=item["description"],
                quantity=(float(item["quantity"]) if item.get("quantity") is not None else None),
                unit=item.get("unit"),
                confidence=(
                    float(item["confidence"]) if item.get("confidence") is not None else None
                ),
                requires_review=bool(item["requires_review"]),
                provenance=ScopeImpactProvenance(
                    technical_delta_id=item["provenance"]["technical_delta_id"],
                    baseline_item_id=item["provenance"].get("baseline_item_id"),
                    decision_id=item["provenance"].get("decision_id"),
                    review_event_id=item["provenance"].get("review_event_id"),
                    accepted_claim_ids=tuple(item["provenance"].get("accepted_claim_ids", [])),
                    authority_decision_ids=tuple(
                        item["provenance"].get("authority_decision_ids", [])
                    ),
                    document_ids=tuple(item["provenance"].get("document_ids", [])),
                    rule_id=item["provenance"].get("rule_id"),
                    rule_set_id=item["provenance"]["rule_set_id"],
                    trace=tuple(item["provenance"].get("trace", [])),
                ),
                fingerprint=item["fingerprint"],
            )
            for item in raw.get("impacts", [])
        ),
    )


class ScopeImpactSummary(TypedDict):
    project_id: str
    baseline_id: str
    total: int
    review_required: int
    by_type: dict[str, int]


def summarize_scope_impacts(result: ScopeImpactSet) -> ScopeImpactSummary:
    by_type: dict[str, int] = {}
    for impact in result.impacts:
        by_type[impact.impact_type.value] = by_type.get(impact.impact_type.value, 0) + 1
    return {
        "project_id": result.project_id,
        "baseline_id": result.baseline_id,
        "total": len(result.impacts),
        "review_required": result.review_required_count,
        "by_type": dict(sorted(by_type.items())),
    }


def build_project_scope_impacts(
    project_file: Path,
    rule_set_file: Path,
    delta_file: Path | None = None,
) -> tuple[ScopeImpactSet, Path]:
    delta_path = delta_file or project_file.with_name("crow-technical-deltas.json")
    deltas = load_delta_set(delta_path)
    rule_set = load_rule_set(rule_set_file)
    result = derive_scope_impacts(deltas, rule_set)
    output = project_file.with_name("crow-scope-impacts.json")
    save_scope_impacts(result, output)
    return result, output
