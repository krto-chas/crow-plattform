"""Source extractors producing SourceTakeoff from each source family.

Every extractor is deterministic and records why a candidate was skipped —
losses are reported, never silently dropped (same principle as the DXF
loss reporting introduced in RC-010).
"""

from __future__ import annotations

import re
from typing import Any

from crow_vent.lexicon import VentLexicon

from .models import (
    LineKind,
    SourceKind,
    SourceLine,
    SourceTakeoff,
    dimension_text,
)

_COUNT_PATTERN = re.compile(
    r"(?P<count>\d+)\s*(?:st|stk|styck)\s+(?P<ident>[A-ZÅÄÖ]{2,4}\d*)", re.IGNORECASE
)
_LENGTH_UNIT_ALIASES = {"m", "lpm", "meter"}
_COUNT_UNIT_ALIASES = {"st", "stk", "styck", "antal"}


def takeoff_from_geometry(payload: dict[str, Any], *, source_id: str) -> SourceTakeoff:
    """Adapt a crow-vent-quantity-v0.3 takeoff payload to source lines."""
    lines: list[SourceLine] = []
    skipped: list[dict[str, Any]] = []
    for row in payload.get("lines", []):
        code = str(row.get("component_code") or "UNCLASSIFIED")
        dimension = str(row.get("dimension") or "Ej angiven")
        label = str(row.get("component_name") or code)
        length = row.get("length_m")
        quantity = row.get("quantity")
        common: dict[str, Any] = {
            "source_id": source_id,
            "source_kind": SourceKind.GEOMETRY,
            "code": code,
            "label": label,
            "dimension": dimension,
            "confidence": 1.0,
            "evidence": {
                "rule": "geometry_takeoff_v0_3",
                "system_ids": list(row.get("system_ids", [])),
            },
        }
        if length is not None:
            lines.append(SourceLine(kind=LineKind.DUCT, quantity=float(length), unit="m", **common))
        elif quantity:
            lines.append(
                SourceLine(kind=LineKind.COMPONENT, quantity=float(quantity), unit="st", **common)
            )
        else:
            skipped.append({"reason": "no_quantity", "row": {"code": code, "dimension": dimension}})
    return SourceTakeoff(source_id, SourceKind.GEOMETRY, tuple(lines), tuple(skipped))


def takeoff_from_table(
    rows: list[list[Any]], *, source_id: str, lexicon: VentLexicon | None = None
) -> SourceTakeoff:
    """Extract lines from spreadsheet rows (XLSX/CSV via the import framework).

    Strategy: for each row, find the first cell the lexicon recognises as a
    duct string or component identity, then take the nearest numeric cell to
    its right as the quantity and any unit-looking cell as the unit.
    """
    lex = lexicon or VentLexicon.default()
    lines: list[SourceLine] = []
    skipped: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        cells = [str(cell).strip() if cell is not None else "" for cell in row]
        match_cell = None
        duct = component = None
        for col_index, text in enumerate(cells):
            if not text:
                continue
            duct = lex.parse_duct_string(text)
            if duct is not None:
                match_cell = col_index
                break
            component = lex.lookup_component(text)
            if component is not None:
                match_cell = col_index
                break
        if match_cell is None:
            if any(cells):
                skipped.append({"reason": "no_lexicon_match", "row_index": row_index})
            continue
        quantity, unit = _numeric_after(cells, match_cell)
        if quantity is None:
            skipped.append({"reason": "no_quantity_cell", "row_index": row_index})
            continue
        if duct is not None:
            dim = duct.dimension
            lines.append(
                SourceLine(
                    source_id=source_id,
                    source_kind=SourceKind.TABLE,
                    kind=LineKind.DUCT,
                    code=duct.medium_code,
                    label=duct.medium_label,
                    dimension=dimension_text(
                        dim.shape, dim.diameter_mm, dim.width_mm, dim.height_mm
                    ),
                    quantity=quantity,
                    unit=unit or "m",
                    confidence=duct.confidence,
                    evidence={"rule": "table_duct_string", "row_index": row_index, **duct.evidence},
                )
            )
        elif component is not None:
            lines.append(
                SourceLine(
                    source_id=source_id,
                    source_kind=SourceKind.TABLE,
                    kind=LineKind.COMPONENT,
                    code=component.code,
                    label=component.label,
                    dimension="Ej angiven",
                    quantity=quantity,
                    unit=unit or "st",
                    confidence=component.confidence,
                    evidence={
                        "rule": "table_component_id",
                        "row_index": row_index,
                        **dict(component.evidence),
                    },
                )
            )
    return SourceTakeoff(source_id, SourceKind.TABLE, tuple(lines), tuple(skipped))


def takeoff_from_text(
    segments: list[str], *, source_id: str, lexicon: VentLexicon | None = None
) -> SourceTakeoff:
    """Extract component counts from specification text (PDF/DOCX segments).

    Matches the pattern "<antal> st <beteckning>" and validates the
    identity against the lexicon. Duct strings without adjacent lengths in
    prose are recorded as skipped mentions rather than quantities.
    """
    lex = lexicon or VentLexicon.default()
    lines: list[SourceLine] = []
    skipped: list[dict[str, Any]] = []
    for segment_index, segment in enumerate(segments):
        for match in _COUNT_PATTERN.finditer(segment):
            component = lex.lookup_component(match.group("ident"))
            if component is None:
                skipped.append(
                    {
                        "reason": "unknown_identity",
                        "segment_index": segment_index,
                        "text": match.group(0),
                    }
                )
                continue
            lines.append(
                SourceLine(
                    source_id=source_id,
                    source_kind=SourceKind.TEXT,
                    kind=LineKind.COMPONENT,
                    code=component.code,
                    label=component.label,
                    dimension="Ej angiven",
                    quantity=float(match.group("count")),
                    unit="st",
                    confidence=round(component.confidence * 0.9, 2),
                    evidence={
                        "rule": "text_count_pattern",
                        "segment_index": segment_index,
                        "matched_text": match.group(0),
                    },
                )
            )
        if lex.parse_duct_string(segment.strip()) is not None:
            skipped.append(
                {
                    "reason": "duct_mention_without_length",
                    "segment_index": segment_index,
                    "text": segment.strip(),
                }
            )
    return SourceTakeoff(source_id, SourceKind.TEXT, tuple(lines), tuple(skipped))


def _numeric_after(cells: list[str], start: int) -> tuple[float | None, str | None]:
    quantity: float | None = None
    unit: str | None = None
    for text in cells[start + 1 :]:
        lowered = text.lower().replace(",", ".")
        if lowered in _LENGTH_UNIT_ALIASES or lowered in _COUNT_UNIT_ALIASES:
            unit = "m" if lowered in _LENGTH_UNIT_ALIASES else "st"
            if quantity is not None:
                break
            continue
        if quantity is None:
            try:
                quantity = float(lowered)
            except ValueError:
                continue
            if unit is not None:
                break
    return quantity, unit
