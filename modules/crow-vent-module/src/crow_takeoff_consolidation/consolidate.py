"""Reconcile source takeoffs into one consolidated bill of quantities.

Rules:
- Lines merge on (kind, code, dimension).
- Counts must agree exactly; lengths within a relative tolerance
  (default 2 %) measured against the highest-confidence source.
- Sources with mismatching units never average — the line is flagged
  UNIT_MISMATCH and excluded from totals until resolved.
- Discrepant lines produce client questions instead of silent choices:
  the consolidation never invents a quantity the sources cannot support.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import (
    SCHEMA_VERSION,
    LineStatus,
    SourceLine,
    SourceTakeoff,
    line_id,
)

DEFAULT_LENGTH_TOLERANCE = 0.02


def consolidate_takeoffs(
    takeoffs: list[SourceTakeoff], *, length_tolerance: float = DEFAULT_LENGTH_TOLERANCE
) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[SourceLine]] = defaultdict(list)
    for takeoff in takeoffs:
        for line in takeoff.lines:
            grouped[line.line_key].append(line)

    lines: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    status_counts: dict[str, int] = defaultdict(int)

    for key in sorted(grouped):
        source_lines = sorted(grouped[key], key=lambda item: (-item.confidence, item.source_id))
        reference = source_lines[0]
        units = {line.unit for line in source_lines}
        quantities = [line.quantity for line in source_lines]

        if len(units) > 1:
            status = LineStatus.UNIT_MISMATCH
            selected: float | None = None
        elif len(source_lines) == 1:
            status = LineStatus.SINGLE_SOURCE
            selected = reference.quantity
        elif _agrees(reference, quantities, length_tolerance):
            status = LineStatus.CORROBORATED
            selected = reference.quantity
        else:
            status = LineStatus.DISCREPANT
            selected = None

        status_counts[status.value] += 1
        entry = {
            "line_id": line_id(key),
            "kind": key[0],
            "code": key[1],
            "dimension": key[2],
            "label": reference.label,
            "unit": reference.unit,
            "status": status.value,
            "selected_quantity": selected,
            "sources": [
                {
                    "source_id": line.source_id,
                    "source_kind": line.source_kind.value,
                    "quantity": line.quantity,
                    "unit": line.unit,
                    "confidence": line.confidence,
                    "evidence": line.evidence,
                }
                for line in source_lines
            ],
        }
        lines.append(entry)

        if status in (LineStatus.DISCREPANT, LineStatus.UNIT_MISMATCH):
            spread = ", ".join(
                f"{line.source_id}: {line.quantity:g} {line.unit}" for line in source_lines
            )
            questions.append(
                {
                    "line_id": entry["line_id"],
                    "question": (
                        f"Mängduppgifterna för {reference.label} {key[2]} skiljer sig "
                        f"mellan handlingarna ({spread}). Vilken uppgift gäller?"
                    ),
                    "status": status.value,
                }
            )

    skipped = [
        {"source_id": takeoff.source_id, **item} for takeoff in takeoffs for item in takeoff.skipped
    ]
    resolved = [line for line in lines if line["selected_quantity"] is not None]
    return {
        "schema_version": SCHEMA_VERSION,
        "source_count": len(takeoffs),
        "line_count": len(lines),
        "status_counts": dict(sorted(status_counts.items())),
        "total_duct_length_m": round(
            sum(
                line["selected_quantity"]
                for line in resolved
                if line["kind"] == "duct" and line["unit"] == "m"
            ),
            3,
        ),
        "total_component_count": round(
            sum(
                line["selected_quantity"]
                for line in resolved
                if line["kind"] == "component" and line["unit"] == "st"
            )
        ),
        "client_questions": questions,
        "skipped": skipped,
        "lines": lines,
    }


def _agrees(reference: SourceLine, quantities: list[float], tolerance: float) -> bool:
    if reference.unit == "st":
        return len({round(quantity) for quantity in quantities}) == 1
    baseline = reference.quantity
    if baseline == 0:
        return all(quantity == 0 for quantity in quantities)
    return all(abs(quantity - baseline) / baseline <= tolerance for quantity in quantities)
