"""Bygger ett deterministiskt OVK-prisförslag ur förfrågan och taxa."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .models import (
    SCHEMA_VERSION,
    BuildingCategory,
    InspectionType,
    OvkObjectPart,
    OvkQuote,
    OvkQuoteLine,
    OvkQuoteRequest,
    PricingBasis,
)
from .taxa import OvkTaxa

_MONEY_QUANTUM = Decimal("0.01")

_INSPECTION_LABELS = {
    InspectionType.FORSTAGANG: "förstagångsbesiktning",
    InspectionType.ATERKOMMANDE: "återkommande besiktning",
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _quantity_for(part: OvkObjectPart, basis: PricingBasis) -> Decimal:
    if basis is PricingBasis.PER_APARTMENT:
        if part.apartment_count is None:
            raise ValueError(
                "apartment_count is required for category "
                f"{part.category.value!r} (basis per_apartment)"
            )
        if part.apartment_count < 1:
            raise ValueError(f"apartment_count must be >= 1, got {part.apartment_count}")
        return Decimal(part.apartment_count)
    if basis is PricingBasis.PER_ROOM:
        if part.room_count is None:
            raise ValueError(
                f"room_count is required for category {part.category.value!r} (basis per_room)"
            )
        if part.room_count < 1:
            raise ValueError(f"room_count must be >= 1, got {part.room_count}")
        return Decimal(part.room_count)
    if basis is PricingBasis.PER_AREA:
        if part.area_m2 is None:
            raise ValueError(
                f"area_m2 is required for category {part.category.value!r} (basis per_area)"
            )
        if part.area_m2 <= 0:
            raise ValueError(f"area_m2 must be positive, got {part.area_m2}")
        return part.area_m2
    if part.unit_count < 1:
        raise ValueError(f"unit_count must be >= 1, got {part.unit_count}")
    return Decimal(part.unit_count)


def _line_for(part: OvkObjectPart, inspection_type: InspectionType, taxa: OvkTaxa) -> OvkQuoteLine:
    if part.category is BuildingCategory.SMAHUS and inspection_type is InspectionType.ATERKOMMANDE:
        raise ValueError(
            "smahus har endast förstagångsbesiktning enligt BFS 2011:16; "
            "återkommande besiktning kan inte prissättas för kategorin"
        )
    basis = taxa.basis(part.category)
    quantity = _quantity_for(part, basis)
    rate = taxa.rate(part.category, inspection_type, part.system_type)
    part_label = part.label if part.label is not None else taxa.label(part.category)
    return OvkQuoteLine(
        category=part.category,
        pricing_basis=basis,
        description=f"OVK {_INSPECTION_LABELS[inspection_type]}, {part_label}",
        quantity=quantity,
        unit=taxa.unit(part.category),
        unit_price=rate,
        amount=_money(quantity * rate),
        recurring_interval_years=taxa.recurring_interval_years(
            part.category, part.system_type, school_or_care=part.school_or_care
        ),
    )


def build_quote(request: OvkQuoteRequest, taxa: OvkTaxa) -> OvkQuote:
    if not request.parts:
        raise ValueError("request must contain at least one object part")

    lines = tuple(_line_for(part, request.inspection_type, taxa) for part in request.parts)

    base_fee = _money(taxa.base_fee)
    subtotal = _money(sum((line.amount for line in lines), Decimal(0)))
    raw_total = base_fee + subtotal
    minimum_total = _money(taxa.minimum_total)
    minimum_applied = raw_total < minimum_total
    total = minimum_total if minimum_applied else _money(raw_total)

    known_intervals = [
        line.recurring_interval_years for line in lines if line.recurring_interval_years is not None
    ]

    return OvkQuote(
        schema_version=SCHEMA_VERSION,
        inspection_type=request.inspection_type,
        lines=lines,
        base_fee=base_fee,
        subtotal=subtotal,
        minimum_total=minimum_total,
        minimum_applied=minimum_applied,
        total=total,
        currency=taxa.currency,
        next_inspection_interval_years=min(known_intervals) if known_intervals else None,
    )


def quote_to_payload(quote: OvkQuote) -> dict[str, Any]:
    """JSON-vänlig payload; belopp serialiseras som strängar (ADR-0009-andan)."""
    return {
        "schema_version": quote.schema_version,
        "inspection_type": quote.inspection_type.value,
        "lines": [
            {
                "category": line.category.value,
                "pricing_basis": line.pricing_basis.value,
                "description": line.description,
                "quantity": str(line.quantity),
                "unit": line.unit,
                "unit_price": str(line.unit_price),
                "amount": str(line.amount),
                "recurring_interval_years": line.recurring_interval_years,
            }
            for line in quote.lines
        ],
        "base_fee": str(quote.base_fee),
        "subtotal": str(quote.subtotal),
        "minimum_total": str(quote.minimum_total),
        "minimum_applied": quote.minimum_applied,
        "total": str(quote.total),
        "currency": quote.currency,
        "next_inspection_interval_years": quote.next_inspection_interval_years,
    }
