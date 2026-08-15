from decimal import Decimal

import pytest

from crow_vent_quote import VentQuoteRequest, build_vent_quote, quote_to_payload


def _priced(*, unpriced: int = 0, reservations: int = 0) -> dict[str, object]:
    return {
        "schema_version": "crow-takeoff-pricing-v0.1",
        "price_book_id": "test-book",
        "currency": "SEK",
        "priced_line_count": 2,
        "unpriced_line_count": unpriced,
        "reservation_count": reservations,
        "grand_total": 100000.0,
    }


def _request() -> VentQuoteRequest:
    return VentQuoteRequest(
        project_name="Projekt A",
        customer_name="Kund AB",
        quote_date="2026-08-08",
        validity_days=30,
        overhead_percent=Decimal("10"),
        risk_percent=Decimal("5"),
        profit_percent=Decimal("15"),
    )


def test_quote_uses_explicit_adjustments_on_base_cost() -> None:
    quote = build_vent_quote(_priced(), _request())
    payload = quote_to_payload(quote)
    assert payload["base_cost"] == "100000.00"
    assert payload["overhead_amount"] == "10000.00"
    assert payload["risk_amount"] == "5000.00"
    assert payload["profit_amount"] == "15000.00"
    assert payload["offer_total"] == "130000.00"
    assert payload["ready_to_send"] is True


def test_quote_is_not_sendable_with_unresolved_pricing() -> None:
    quote = build_vent_quote(_priced(unpriced=1, reservations=2), _request())
    assert quote.ready_to_send is False


def test_negative_adjustment_is_rejected() -> None:
    request = VentQuoteRequest(
        project_name="Projekt A",
        customer_name="Kund AB",
        quote_date="2026-08-08",
        validity_days=30,
        profit_percent=Decimal("-1"),
    )
    with pytest.raises(ValueError, match="profit_percent"):
        build_vent_quote(_priced(), request)


def test_wrong_pricing_schema_is_rejected() -> None:
    with pytest.raises(ValueError, match="crow-takeoff-pricing"):
        build_vent_quote({"schema_version": "wrong"}, _request())
