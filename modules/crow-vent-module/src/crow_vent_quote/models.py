from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class VentQuoteRequest:
    project_name: str
    customer_name: str
    quote_date: str
    validity_days: int
    overhead_percent: Decimal = Decimal("0")
    risk_percent: Decimal = Decimal("0")
    profit_percent: Decimal = Decimal("0")
    scope_note: str = ""
    exclusions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VentQuote:
    schema_version: str
    project_name: str
    customer_name: str
    quote_date: str
    validity_days: int
    currency: str
    base_cost: Decimal
    overhead_percent: Decimal
    overhead_amount: Decimal
    risk_percent: Decimal
    risk_amount: Decimal
    profit_percent: Decimal
    profit_amount: Decimal
    offer_total: Decimal
    priced_line_count: int
    unpriced_line_count: int
    reservation_count: int
    ready_to_send: bool
    scope_note: str
    exclusions: tuple[str, ...]
    source_price_book_id: str
