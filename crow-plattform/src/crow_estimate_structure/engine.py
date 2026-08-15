from __future__ import annotations

import hashlib
import math
from collections import defaultdict

from crow_estimate_line import Estimate, EstimateLine

from .models import (
    BillOfQuantityLine,
    EstimateGroup,
    EstimateGroupingProfile,
    EstimateGroupingRule,
    EstimateSection,
    StructuredEstimate,
)


def _hash(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def _match(line: EstimateLine, rule: EstimateGroupingRule) -> bool:
    cost_ok = not rule.cost_types or (line.cost_type or "") in rule.cost_types
    text = line.description.casefold()
    desc_ok = not rule.description_contains or any(
        token.casefold() in text for token in rule.description_contains
    )
    return cost_ok and desc_ok


def _select(line: EstimateLine, profile: EstimateGroupingProfile) -> tuple[str, str, str, str]:
    rules = sorted(profile.rules, key=lambda r: (r.priority, r.id))
    for rule in rules:
        if _match(line, rule):
            return rule.section_code, rule.section_title, rule.group_code, rule.group_title
    return (
        profile.fallback_section_code,
        profile.fallback_section_title,
        profile.fallback_group_code,
        profile.fallback_group_title,
    )


def structure_estimate(
    estimate: Estimate, profile: EstimateGroupingProfile, structure_id: str
) -> StructuredEstimate:
    buckets: dict[tuple[str, str, str, str], list[EstimateLine]] = defaultdict(list)
    for line in estimate.lines:
        buckets[_select(line, profile)].append(line)

    sections_data: dict[tuple[str, str], list[tuple[str, str, list[EstimateLine]]]] = defaultdict(
        list
    )
    for (sc, st, gc, gt), lines in buckets.items():
        sections_data[(sc, st)].append((gc, gt, lines))

    sections: list[EstimateSection] = []
    all_ids: list[str] = []
    for section_index, ((sc, st), groups_raw) in enumerate(sorted(sections_data.items()), start=1):
        groups: list[EstimateGroup] = []
        section_ids: list[str] = []
        section_docs: set[str] = set()
        for group_index, (gc, gt, source_lines) in enumerate(
            sorted(groups_raw, key=lambda x: (x[0], x[1])), start=1
        ):
            boq_lines: list[BillOfQuantityLine] = []
            group_docs: set[str] = set()
            group_ids: list[str] = []
            for line_index, line in enumerate(sorted(source_lines, key=lambda x: x.id), start=1):
                position = f"{section_index}.{group_index}.{line_index}"
                fp = _hash(structure_id, position, line.id, line.fingerprint)
                boq_lines.append(
                    BillOfQuantityLine(
                        id=f"boq-line:{fp}",
                        position=position,
                        estimate_line_id=line.id,
                        description=line.description,
                        quantity=line.quantity,
                        unit=line.unit,
                        unit_rate=line.unit_rate,
                        net_amount=line.net_amount,
                        adjustment_amount=line.adjustment_amount,
                        total_amount=line.total_amount,
                        currency=line.currency,
                        fingerprint=fp,
                    )
                )
                group_ids.append(line.id)
                group_docs.update(line.provenance.document_ids)
            net = sum(x.net_amount for x in boq_lines)
            adj = sum(x.adjustment_amount for x in boq_lines)
            total = sum(x.total_amount for x in boq_lines)
            gfp = _hash(structure_id, sc, gc, *group_ids, net, adj, total)
            group = EstimateGroup(
                id=f"estimate-group:{gfp}",
                code=gc,
                title=gt,
                position=f"{section_index}.{group_index}",
                lines=tuple(boq_lines),
                estimate_line_ids=tuple(group_ids),
                document_ids=tuple(sorted(group_docs)),
                net_total=net,
                adjustment_total=adj,
                grand_total=total,
                fingerprint=gfp,
            )
            groups.append(group)
            section_ids.extend(group_ids)
            section_docs.update(group_docs)
        net = sum(x.net_total for x in groups)
        adj = sum(x.adjustment_total for x in groups)
        total = sum(x.grand_total for x in groups)
        sfp = _hash(structure_id, sc, *section_ids, net, adj, total)
        sections.append(
            EstimateSection(
                id=f"estimate-section:{sfp}",
                code=sc,
                title=st,
                position=str(section_index),
                groups=tuple(groups),
                estimate_line_ids=tuple(section_ids),
                document_ids=tuple(sorted(section_docs)),
                net_total=net,
                adjustment_total=adj,
                grand_total=total,
                fingerprint=sfp,
            )
        )
        all_ids.extend(section_ids)

    if sorted(all_ids) != sorted(line.id for line in estimate.lines):
        raise ValueError("Every estimate line must occur exactly once")
    result_fp = _hash(
        structure_id,
        estimate.estimate_id,
        profile.id,
        *(section.fingerprint for section in sections),
    )
    result = StructuredEstimate(
        project_id=estimate.project_id,
        baseline_id=estimate.baseline_id,
        estimate_id=estimate.estimate_id,
        structure_id=structure_id,
        grouping_profile_id=profile.id,
        currency=estimate.currency,
        sections=tuple(sections),
        source_line_ids=tuple(sorted(all_ids)),
        fingerprint=result_fp,
    )
    if not math.isclose(result.grand_total, estimate.grand_total, abs_tol=1e-6):
        raise ValueError("Structured estimate total does not match source estimate")
    return result
