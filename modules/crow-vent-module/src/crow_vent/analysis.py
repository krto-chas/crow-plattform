from __future__ import annotations

from collections import Counter
from hashlib import sha256
from typing import Any


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256(":".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def infer_system_kind(components: list[dict[str, Any]]) -> tuple[str, float]:
    roles = [str(item["airflow_role"]) for item in components if item.get("airflow_role")]
    if not roles:
        return "unknown", 0.25
    counts = Counter(roles)
    role, count = counts.most_common(1)[0]
    purity = count / len(roles)
    mapping = {
        "supply": "tilluft",
        "extract": "frånluft",
        "transfer": "överluft",
        "outdoor": "uteluft",
        "exhaust": "avluft",
    }
    return mapping.get(role, role), round(purity, 4)


def build_relations(system_id: str, components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    units = [item for item in components if item.get("category") in {"unit", "fan"}]
    terminals = [item for item in components if item.get("category") == "terminal"]
    inline = [
        item
        for item in components
        if item.get("category") in {"damper", "silencer", "filter", "coil"}
    ]

    for terminal in terminals:
        for source in units[:1]:
            relations.append(
                {
                    "relation_id": _stable_id(
                        "vent-relation",
                        system_id,
                        source["classification_id"],
                        terminal["classification_id"],
                    ),
                    "relation_type": "serves",
                    "from_classification_id": source["classification_id"],
                    "to_classification_id": terminal["classification_id"],
                    "confidence": round(
                        min(source["confidence"], terminal["confidence"]) * 0.85, 4
                    ),
                    "basis": "same_geometry_system",
                }
            )
    for component in inline:
        relations.append(
            {
                "relation_id": _stable_id(
                    "vent-relation", system_id, component["classification_id"]
                ),
                "relation_type": "inline_component",
                "from_classification_id": component["classification_id"],
                "to_classification_id": f"vent:{system_id}",
                "confidence": round(component["confidence"] * 0.8, 4),
                "basis": "same_geometry_system",
            }
        )
    return relations


def analyse_system(system_id: str, components: list[dict[str, Any]]) -> dict[str, Any]:
    kind, purity = infer_system_kind(components)
    roles = sorted({item["airflow_role"] for item in components if item.get("airflow_role")})
    categories = Counter(item.get("category") or "unknown" for item in components)
    findings: list[dict[str, Any]] = []

    def add(code: str, severity: str, title: str, detail: str, refs: list[str]) -> None:
        findings.append(
            {
                "finding_id": _stable_id("vent-finding", system_id, code, *refs),
                "code": code,
                "severity": severity,
                "title": title,
                "detail": detail,
                "classification_ids": refs,
                "status": "open",
            }
        )

    unresolved = [item for item in components if item.get("status") != "classified"]
    if unresolved:
        add(
            "VENT.UNRESOLVED_COMPONENT",
            "warning",
            "Oklassificerade komponenter",
            f"{len(unresolved)} komponenter behöver granskas innan systemet kan fastställas.",
            [item["classification_id"] for item in unresolved],
        )
    if (
        len(roles) > 1
        and not set(roles).issubset({"outdoor", "supply"})
        and not set(roles).issubset({"extract", "exhaust"})
    ):
        add(
            "VENT.MIXED_AIRFLOW_ROLES",
            "warning",
            "Blandade luftslag",
            "Systemet innehåller komponenter med luftslag som normalt inte tillhör samma kanalnät.",
            [item["classification_id"] for item in components if item.get("airflow_role")],
        )
    terminals = [item for item in components if item.get("category") == "terminal"]
    units = [item for item in components if item.get("category") in {"unit", "fan"}]
    if terminals and not units:
        add(
            "VENT.NO_SOURCE_COMPONENT",
            "info",
            "Ingen fläkt eller aggregat identifierat",
            "Systemet har don men ingen säker källa inom det analyserade geometrisystemet.",
            [item["classification_id"] for item in terminals],
        )
    if categories.get("damper", 0) and not terminals and not units:
        add(
            "VENT.ISOLATED_INLINE_COMPONENTS",
            "warning",
            "Isolerade kanalkomponenter",
            "Spjäll eller andra inline-komponenter saknar identifierad anslutning "
            "till don eller aggregat.",
            [item["classification_id"] for item in components if item.get("category") == "damper"],
        )

    relations = build_relations(system_id, components)
    status = (
        "needs_review"
        if any(item["severity"] == "warning" for item in findings) or unresolved
        else "analysed"
    )
    return {
        "system_kind": kind,
        "system_confidence": purity,
        "airflow_roles": roles,
        "category_counts": dict(sorted(categories.items())),
        "relations": relations,
        "relation_count": len(relations),
        "findings": findings,
        "finding_count": len(findings),
        "analysis_status": status,
    }
