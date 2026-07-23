"""Price a consolidated takeoff against a price book — the base estimate.

This closes the chain handling → delmängd → kalkylrad: resolved
consolidated lines are matched against price book entries on the same
(kind, code, dimension) key, yielding material and labour amounts per line
and project totals in SEK.

Principles carried through:
- Only resolved lines (corroborated or single_source with a selected
  quantity) are priced. Discrepant and unit-mismatch lines are excluded
  from totals and surfaced as reservations — the estimate never contains
  a number the sources cannot support.
- Every line that could not be priced is reported with a reason.
  No silent losses.
- Deterministic: same takeoff and price book always produce the same
  payload, line ids reuse the consolidation's SHA-256 ids.

The existing Estimate/EstimateLine chain (commercial impact → estimate)
models change flows (ÄTA) with delta-anchored provenance; the base
takeoff estimate is a different provenance shape, so it gets its own
schema here. An adapter into EstimateRevision comparison is future work
once provenance is generalised.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import SCHEMA_VERSION as CONSOLIDATION_SCHEMA

SCHEMA_VERSION = "crow-takeoff-pricing-v0.1"
WILDCARD_DIMENSION = "*"


@dataclass(frozen=True)
class PriceBookEntry:
    kind: str
    code: str
    dimension: str
    unit: str
    material_unit_price: float
    labour_hours_per_unit: float = 0.0
    article: str | None = None

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.kind, self.code, self.dimension)


@dataclass(frozen=True)
class PriceBook:
    price_book_id: str
    currency: str = "SEK"
    labour_rate_per_hour: float = 0.0
    entries: tuple[PriceBookEntry, ...] = field(default_factory=tuple)

    def lookup(self, kind: str, code: str, dimension: str) -> PriceBookEntry | None:
        exact = {entry.key: entry for entry in self.entries}
        found = exact.get((kind, code, dimension))
        if found is not None:
            return found
        return exact.get((kind, code, WILDCARD_DIMENSION))


def price_consolidated_takeoff(
    consolidated: dict[str, Any], price_book: PriceBook
) -> dict[str, Any]:
    if not str(consolidated.get("schema_version", "")).startswith("crow-takeoff-consolidation"):
        raise ValueError(
            f"Expected a {CONSOLIDATION_SCHEMA} payload, "
            f"got schema_version={consolidated.get('schema_version')!r}"
        )

    priced: list[dict[str, Any]] = []
    unpriced: list[dict[str, Any]] = []
    reservations: list[dict[str, Any]] = []
    material_total = 0.0
    labour_hours_total = 0.0

    for line in consolidated.get("lines", []):
        base = {
            "line_id": line["line_id"],
            "kind": line["kind"],
            "code": line["code"],
            "dimension": line["dimension"],
            "label": line["label"],
        }
        if line["selected_quantity"] is None:
            reservations.append(
                {
                    **base,
                    "status": line["status"],
                    "reason": "unresolved_quantity",
                }
            )
            continue
        entry = price_book.lookup(line["kind"], line["code"], line["dimension"])
        if entry is None:
            unpriced.append({**base, "reason": "no_price_entry", "unit": line["unit"]})
            continue
        if entry.unit != line["unit"]:
            unpriced.append(
                {
                    **base,
                    "reason": "price_unit_mismatch",
                    "line_unit": line["unit"],
                    "price_unit": entry.unit,
                }
            )
            continue

        quantity = float(line["selected_quantity"])
        material_amount = round(quantity * entry.material_unit_price, 2)
        labour_hours = round(quantity * entry.labour_hours_per_unit, 3)
        labour_amount = round(labour_hours * price_book.labour_rate_per_hour, 2)
        material_total += material_amount
        labour_hours_total += labour_hours
        priced.append(
            {
                **base,
                "article": entry.article,
                "quantity": quantity,
                "unit": entry.unit,
                "material_unit_price": entry.material_unit_price,
                "material_amount": material_amount,
                "labour_hours_per_unit": entry.labour_hours_per_unit,
                "labour_hours": labour_hours,
                "labour_amount": labour_amount,
                "line_total": round(material_amount + labour_amount, 2),
                "source_status": line["status"],
            }
        )

    labour_total = round(labour_hours_total * price_book.labour_rate_per_hour, 2)
    return {
        "schema_version": SCHEMA_VERSION,
        "price_book_id": price_book.price_book_id,
        "currency": price_book.currency,
        "labour_rate_per_hour": price_book.labour_rate_per_hour,
        "priced_line_count": len(priced),
        "unpriced_line_count": len(unpriced),
        "reservation_count": len(reservations),
        "material_total": round(material_total, 2),
        "labour_hours_total": round(labour_hours_total, 3),
        "labour_total": labour_total,
        "grand_total": round(material_total + labour_total, 2),
        "lines": priced,
        "unpriced": unpriced,
        "reservations": reservations,
        "client_questions": list(consolidated.get("client_questions", [])),
    }
