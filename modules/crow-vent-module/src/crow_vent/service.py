from __future__ import annotations

from collections import defaultdict
from typing import Any

from .analysis import analyse_system
from .classification import classify_candidates
from .quantity import build_quantity_takeoff


def build_vent_model(candidates: dict[str, Any]) -> dict[str, Any]:
    result = classify_candidates(candidates)
    systems: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in result["classifications"]:
        systems[item["system_id"]].append(item)

    model_systems: list[dict[str, Any]] = []
    all_findings: list[dict[str, Any]] = []
    all_relations: list[dict[str, Any]] = []
    for system_id, items in sorted(systems.items()):
        analysis = analyse_system(system_id, items)
        statuses = [item["status"] for item in items]
        classification_status = (
            "classified"
            if statuses and all(status == "classified" for status in statuses)
            else "needs_review"
        )
        system = {
            "vent_system_id": f"vent:{system_id}",
            "geometry_system_id": system_id,
            "airflow_role": max(
                (role for role in analysis["airflow_roles"]),
                key=lambda role: sum(1 for item in items if item.get("airflow_role") == role),
                default=None,
            ),
            "system_kind": analysis["system_kind"],
            "system_confidence": analysis["system_confidence"],
            "status": "needs_review"
            if analysis["analysis_status"] == "needs_review"
            else classification_status,
            "component_count": len(items),
            "components": items,
            **{
                key: value
                for key, value in analysis.items()
                if key not in {"system_kind", "system_confidence"}
            },
        }
        model_systems.append(system)
        all_findings.extend(analysis["findings"])
        all_relations.extend(analysis["relations"])

    quantity_takeoff = build_quantity_takeoff(model_systems)

    return {
        **result,
        "vent_schema_version": "crow-vent-v0.3",
        "system_count": len(model_systems),
        "relation_count": len(all_relations),
        "finding_count": len(all_findings),
        "systems": model_systems,
        "relations": all_relations,
        "findings": all_findings,
        "quantity_takeoff": quantity_takeoff,
        "summary": {
            "systems_ready": sum(
                1 for system in model_systems if system["status"] != "needs_review"
            ),
            "systems_needing_review": sum(
                1 for system in model_systems if system["status"] == "needs_review"
            ),
            "warnings": sum(1 for finding in all_findings if finding["severity"] == "warning"),
            "information": sum(1 for finding in all_findings if finding["severity"] == "info"),
        },
    }
