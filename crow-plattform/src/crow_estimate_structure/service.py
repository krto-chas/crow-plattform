from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypedDict

from crow_estimate_line import load_estimate

from .engine import structure_estimate
from .models import (
    EstimateGroupingProfile,
    EstimateGroupingRule,
    StructuredEstimate,
)


def load_grouping_profile(path: Path) -> EstimateGroupingProfile:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return EstimateGroupingProfile(
        id=raw["id"],
        rules=tuple(
            EstimateGroupingRule(
                id=r["id"],
                section_code=r["section_code"],
                section_title=r["section_title"],
                group_code=r["group_code"],
                group_title=r["group_title"],
                cost_types=tuple(r.get("cost_types", [])),
                description_contains=tuple(r.get("description_contains", [])),
                priority=int(r.get("priority", 100)),
            )
            for r in raw.get("rules", [])
        ),
        fallback_section_code=raw.get("fallback_section_code", "99"),
        fallback_section_title=raw.get("fallback_section_title", "Övrigt"),
        fallback_group_code=raw.get("fallback_group_code", "99"),
        fallback_group_title=raw.get("fallback_group_title", "Ej klassificerat"),
    )


def load_structured_estimate(path: Path) -> StructuredEstimate:
    from .models import BillOfQuantityLine, EstimateGroup, EstimateSection

    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    sections = []
    for section in raw.get("sections", []):
        groups = []
        for group in section.get("groups", []):
            lines = tuple(
                BillOfQuantityLine(
                    id=line["id"],
                    position=line["position"],
                    estimate_line_id=line["estimate_line_id"],
                    description=line["description"],
                    quantity=float(line["quantity"]),
                    unit=line["unit"],
                    unit_rate=float(line["unit_rate"]),
                    net_amount=float(line["net_amount"]),
                    adjustment_amount=float(line["adjustment_amount"]),
                    total_amount=float(line["total_amount"]),
                    currency=line["currency"],
                    fingerprint=line["fingerprint"],
                )
                for line in group.get("lines", [])
            )
            groups.append(
                EstimateGroup(
                    id=group["id"],
                    code=group["code"],
                    title=group["title"],
                    position=group["position"],
                    lines=lines,
                    estimate_line_ids=tuple(group.get("estimate_line_ids", [])),
                    document_ids=tuple(group.get("document_ids", [])),
                    net_total=float(group["net_total"]),
                    adjustment_total=float(group["adjustment_total"]),
                    grand_total=float(group["grand_total"]),
                    fingerprint=group["fingerprint"],
                )
            )
        sections.append(
            EstimateSection(
                id=section["id"],
                code=section["code"],
                title=section["title"],
                position=section["position"],
                groups=tuple(groups),
                estimate_line_ids=tuple(section.get("estimate_line_ids", [])),
                document_ids=tuple(section.get("document_ids", [])),
                net_total=float(section["net_total"]),
                adjustment_total=float(section["adjustment_total"]),
                grand_total=float(section["grand_total"]),
                fingerprint=section["fingerprint"],
            )
        )
    return StructuredEstimate(
        project_id=raw["project_id"],
        baseline_id=raw["baseline_id"],
        estimate_id=raw["estimate_id"],
        structure_id=raw["structure_id"],
        grouping_profile_id=raw["grouping_profile_id"],
        currency=raw["currency"],
        sections=tuple(sections),
        source_line_ids=tuple(raw.get("source_line_ids", [])),
        fingerprint=raw["fingerprint"],
    )


def save_structured_estimate(value: StructuredEstimate, path: Path) -> None:
    payload = json.dumps(asdict(value), ensure_ascii=False, indent=2) + "\n"
    path.write_text(payload, encoding="utf-8")


def write_grouping_profile_template(path: Path) -> None:
    payload = {
        "id": "default-estimate-structure",
        "rules": [
            {
                "id": "labour",
                "section_code": "10",
                "section_title": "Produktion",
                "group_code": "10",
                "group_title": "Arbete",
                "cost_types": ["labour"],
                "priority": 10,
            },
            {
                "id": "material",
                "section_code": "10",
                "section_title": "Produktion",
                "group_code": "20",
                "group_title": "Material",
                "cost_types": ["material"],
                "priority": 20,
            },
            {
                "id": "subcontractor",
                "section_code": "20",
                "section_title": "Underentreprenad",
                "group_code": "10",
                "group_title": "UE",
                "cost_types": ["subcontractor"],
                "priority": 30,
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class StructuredEstimateSummary(TypedDict):
    project_id: str
    estimate_id: str
    structure_id: str
    currency: str
    sections: int
    groups: int
    lines: int
    net_total: float
    adjustment_total: float
    grand_total: float


def summarize_structured_estimate(value: StructuredEstimate) -> StructuredEstimateSummary:
    return {
        "project_id": value.project_id,
        "estimate_id": value.estimate_id,
        "structure_id": value.structure_id,
        "currency": value.currency,
        "sections": len(value.sections),
        "groups": sum(len(s.groups) for s in value.sections),
        "lines": sum(len(g.lines) for s in value.sections for g in s.groups),
        "net_total": value.net_total,
        "adjustment_total": value.adjustment_total,
        "grand_total": value.grand_total,
    }


def build_project_structure(
    project_file: Path,
    structure_id: str,
    profile_file: Path,
    estimate_file: Path | None = None,
) -> tuple[StructuredEstimate, Path]:
    estimate_path = estimate_file or project_file.with_name("crow-estimate.json")
    result = structure_estimate(
        load_estimate(estimate_path), load_grouping_profile(profile_file), structure_id
    )
    output = project_file.with_name("crow-structured-estimate.json")
    save_structured_estimate(result, output)
    return result, output
