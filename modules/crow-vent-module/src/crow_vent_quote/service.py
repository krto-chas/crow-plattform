from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .models import VentQuote, VentQuoteRequest

SCHEMA_VERSION = "crow-vent-quote-v0.1"
_MONEY = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)


def _percent(value: Decimal, name: str) -> Decimal:
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def build_vent_quote(priced_takeoff: dict[str, Any], request: VentQuoteRequest) -> VentQuote:
    schema = str(priced_takeoff.get("schema_version", ""))
    if not schema.startswith("crow-takeoff-pricing"):
        raise ValueError(f"Expected crow-takeoff-pricing payload, got {schema!r}")
    if request.validity_days < 1:
        raise ValueError("validity_days must be >= 1")

    overhead_percent = _percent(request.overhead_percent, "overhead_percent")
    risk_percent = _percent(request.risk_percent, "risk_percent")
    profit_percent = _percent(request.profit_percent, "profit_percent")
    base_cost = _money(Decimal(str(priced_takeoff.get("grand_total", "0"))))

    overhead_amount = _money(base_cost * overhead_percent / Decimal("100"))
    risk_amount = _money(base_cost * risk_percent / Decimal("100"))
    profit_amount = _money(base_cost * profit_percent / Decimal("100"))
    offer_total = _money(base_cost + overhead_amount + risk_amount + profit_amount)

    unpriced_line_count = int(priced_takeoff.get("unpriced_line_count", 0))
    reservation_count = int(priced_takeoff.get("reservation_count", 0))

    return VentQuote(
        schema_version=SCHEMA_VERSION,
        project_name=request.project_name,
        customer_name=request.customer_name,
        quote_date=request.quote_date,
        validity_days=request.validity_days,
        currency=str(priced_takeoff.get("currency", "SEK")),
        base_cost=base_cost,
        overhead_percent=overhead_percent,
        overhead_amount=overhead_amount,
        risk_percent=risk_percent,
        risk_amount=risk_amount,
        profit_percent=profit_percent,
        profit_amount=profit_amount,
        offer_total=offer_total,
        priced_line_count=int(priced_takeoff.get("priced_line_count", 0)),
        unpriced_line_count=unpriced_line_count,
        reservation_count=reservation_count,
        ready_to_send=unpriced_line_count == 0 and reservation_count == 0,
        scope_note=request.scope_note,
        exclusions=request.exclusions,
        source_price_book_id=str(priced_takeoff.get("price_book_id", "")),
    )


def quote_to_payload(quote: VentQuote) -> dict[str, Any]:
    return {
        "schema_version": quote.schema_version,
        "project_name": quote.project_name,
        "customer_name": quote.customer_name,
        "quote_date": quote.quote_date,
        "validity_days": quote.validity_days,
        "currency": quote.currency,
        "base_cost": str(quote.base_cost),
        "overhead_percent": str(quote.overhead_percent),
        "overhead_amount": str(quote.overhead_amount),
        "risk_percent": str(quote.risk_percent),
        "risk_amount": str(quote.risk_amount),
        "profit_percent": str(quote.profit_percent),
        "profit_amount": str(quote.profit_amount),
        "offer_total": str(quote.offer_total),
        "priced_line_count": quote.priced_line_count,
        "unpriced_line_count": quote.unpriced_line_count,
        "reservation_count": quote.reservation_count,
        "ready_to_send": quote.ready_to_send,
        "scope_note": quote.scope_note,
        "exclusions": list(quote.exclusions),
        "source_price_book_id": quote.source_price_book_id,
    }
