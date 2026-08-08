from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

SCHEMA_VERSION = "crow-pressure-test-offer-v0.1"
_MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class ServicePriceEntry:
    code: str
    label: str
    unit: str
    unit_price: Decimal


@dataclass(frozen=True)
class ServicePriceBook:
    price_book_id: str
    currency: str = "SEK"
    entries: tuple[ServicePriceEntry, ...] = field(default_factory=tuple)

    def lookup(self, code: str) -> ServicePriceEntry | None:
        for entry in self.entries:
            if entry.code == code:
                return entry
        return None


@dataclass(frozen=True)
class OfferItemRequest:
    """Manuellt tillagd offertpost utöver strängmodellen (lådor, gjutetapper, timmar)."""

    code: str
    quantity: Decimal
    stairwell_id: str | None = None
    label_override: str | None = None


def default_service_price_book() -> ServicePriceBook:
    """Startprisbok kalibrerad mot Berghällen-anbudet; justerbar per projekt."""
    return ServicePriceBook(
        price_book_id="provtryckning-standard-2026",
        entries=tuple(
            ServicePriceEntry(code, label, unit, Decimal(price))
            for code, label, unit, price in (
                ("provtryckning_strang", "Schaktkanal, provtryckning per sträng", "st", "675"),
                ("samlingslada", "Samlingslåda/samlingskanal inkl. anslutningar", "st", "1500"),
                ("gjutetapp", "Provning ingjutna kanaler per gjutetapp", "st", "1600"),
                ("timme", "Timpris övrig provning", "h", "925"),
                ("etablering", "Etablering per besökstillfälle", "st", "3000"),
                ("slutrapport", "Slutrapport per system", "st", "1500"),
            )
        ),
    )


def _money(value: Decimal) -> str:
    return str(value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP))


def price_pressure_test_offer(
    service_quantities: Mapping[str, Any],
    price_book: ServicePriceBook,
    extra_items: Iterable[OfferItemRequest] = (),
    establishments: int = 0,
    risk_factor: Decimal = Decimal("0.05"),
) -> dict[str, Any]:
    """Prissätter provtryckningsmängder + manuella poster till offertunderlag.

    Poster utan prisbokspost blir reservationer, aldrig tyst nollade.
    Fast pris = totalsumma × (1 + risk), avrundad till närmaste tusenlapp.
    """
    schema = str(service_quantities.get("schema_version", ""))
    if not schema.startswith("crow-riser-service"):
        raise ValueError(f"Expected crow-riser-service payload, got {schema!r}")
    if establishments < 0:
        raise ValueError("establishments must be >= 0")
    if risk_factor < 0:
        raise ValueError("risk_factor must be >= 0")

    lines: list[dict[str, Any]] = []
    reservations: list[dict[str, Any]] = []
    total = Decimal("0")

    def add_line(
        code: str,
        quantity: Decimal,
        stairwell_id: str | None,
        label_override: str | None = None,
    ) -> None:
        nonlocal total
        entry = price_book.lookup(code)
        if entry is None:
            reservations.append(
                {
                    "code": code,
                    "quantity": str(quantity),
                    "stairwell_id": stairwell_id,
                    "reason": "no_price_entry",
                }
            )
            return
        amount = (entry.unit_price * quantity).quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        total += amount
        lines.append(
            {
                "code": code,
                "label": label_override or entry.label,
                "stairwell_id": stairwell_id,
                "quantity": str(quantity),
                "unit": entry.unit,
                "unit_price": _money(entry.unit_price),
                "amount": _money(amount),
            }
        )

    for stairwell in service_quantities.get("stairwells", []):
        add_line(
            "provtryckning_strang",
            Decimal(int(stairwell["strings_to_test"])),
            str(stairwell["stairwell_id"]),
        )
    for item in extra_items:
        add_line(item.code, item.quantity, item.stairwell_id, item.label_override)
    if establishments:
        add_line("etablering", Decimal(establishments), None)

    with_risk = total * (Decimal("1") + risk_factor)
    fixed_price = (with_risk / 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 1000
    return {
        "schema_version": SCHEMA_VERSION,
        "price_book_id": price_book.price_book_id,
        "currency": price_book.currency,
        "lines": lines,
        "reservations": reservations,
        "totals": {
            "itemised_total": _money(total),
            "risk_factor": str(risk_factor),
            "recommended_fixed_price": _money(fixed_price),
        },
    }
