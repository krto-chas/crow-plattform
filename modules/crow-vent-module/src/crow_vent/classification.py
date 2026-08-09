from __future__ import annotations

from hashlib import sha256
from typing import Any

from .models import VentClassification
from .registry import resolve_component


def _id(candidate_group_id: str, code: str | None) -> str:
    digest = sha256(f"{candidate_group_id}:{code or 'unresolved'}".encode()).hexdigest()[:16]
    return f"vent-classification-{digest}"


def classify_candidates(payload: dict[str, Any]) -> dict[str, Any]:
    classifications: list[VentClassification] = []
    for candidate in payload.get("candidates", []):
        value = str(candidate.get("display_value") or candidate.get("normalized_value") or "")
        component = resolve_component(value)
        base = float(candidate.get("score", 0.0))
        confidence = (
            round(min(0.99, base + (0.08 if component else 0.0)), 4)
            if component
            else round(base * 0.35, 4)
        )
        status = (
            "classified"
            if component and confidence >= 0.75 and not candidate.get("conflict")
            else "needs_review"
        )
        classifications.append(
            VentClassification(
                classification_id=_id(
                    str(candidate.get("candidate_group_id")), component.code if component else None
                ),
                system_id=str(candidate.get("system_id")),
                candidate_group_id=str(candidate.get("candidate_group_id")),
                source_value=value,
                component_code=component.code if component else None,
                component_name=component.name_sv if component else None,
                category=component.category if component else None,
                airflow_role=component.airflow_role if component else None,
                confidence=confidence,
                status=status,
                evidence={
                    "geometry_candidate": candidate.get("candidate_group_id"),
                    "observation_ids": candidate.get("observation_ids", []),
                    "candidate_object_ids": candidate.get("candidate_object_ids", []),
                    "geometry_score": base,
                    "registry_match": component.code if component else None,
                    "conflict": bool(candidate.get("conflict")),
                },
            )
        )
    return {
        "vent_schema_version": "crow-vent-v0.2",
        "classification_count": len(classifications),
        "classified_count": sum(1 for item in classifications if item.status == "classified"),
        "review_count": sum(1 for item in classifications if item.status != "classified"),
        "classifications": [item.__dict__ for item in classifications],
    }
