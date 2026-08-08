from __future__ import annotations

from decimal import Decimal

import pytest

from crow_pressure_test import (
    OfferItemRequest,
    ServicePriceBook,
    ServicePriceEntry,
    default_service_price_book,
    price_pressure_test_offer,
)

_QUANTITIES = {
    "schema_version": "crow-riser-service-v0.1",
    "stairwells": [
        {"stairwell_id": "trh-1", "strings_to_test": 24},
        {"stairwell_id": "trh-2", "strings_to_test": 21},
    ],
    "totals": {},
}


def test_strings_priced_per_stairwell_with_default_book() -> None:
    offer = price_pressure_test_offer(_QUANTITIES, default_service_price_book())
    assert len(offer["lines"]) == 2
    amounts = {line["stairwell_id"]: line["amount"] for line in offer["lines"]}
    assert amounts == {"trh-1": "16200.00", "trh-2": "14175.00"}
    assert offer["totals"]["itemised_total"] == "30375.00"


def test_fixed_price_rounds_to_nearest_thousand() -> None:
    offer = price_pressure_test_offer(
        _QUANTITIES, default_service_price_book(), risk_factor=Decimal("0.05")
    )
    assert offer["totals"]["recommended_fixed_price"] == "32000.00"


def test_unknown_code_becomes_reservation_never_zero() -> None:
    offer = price_pressure_test_offer(
        _QUANTITIES,
        default_service_price_book(),
        [OfferItemRequest("specialprovning", Decimal(4))],
    )
    assert offer["reservations"] == [
        {
            "code": "specialprovning",
            "quantity": "4",
            "stairwell_id": None,
            "reason": "no_price_entry",
        }
    ]


def test_extra_items_and_establishments_add_lines() -> None:
    offer = price_pressure_test_offer(
        _QUANTITIES,
        default_service_price_book(),
        [OfferItemRequest("gjutetapp", Decimal(15))],
        establishments=12,
    )
    codes = [line["code"] for line in offer["lines"]]
    assert codes.count("gjutetapp") == 1
    assert codes.count("etablering") == 1
    total = Decimal(offer["totals"]["itemised_total"])
    assert total == Decimal("30375.00") + 15 * 1600 + 12 * 3000


def test_rejects_wrong_schema_and_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        price_pressure_test_offer({"schema_version": "x"}, default_service_price_book())
    with pytest.raises(ValueError):
        price_pressure_test_offer(
            _QUANTITIES, default_service_price_book(), establishments=-1
        )
    with pytest.raises(ValueError):
        price_pressure_test_offer(
            _QUANTITIES, default_service_price_book(), risk_factor=Decimal("-0.1")
        )


def test_custom_price_book_overrides_defaults() -> None:
    book = ServicePriceBook(
        price_book_id="egen",
        entries=(ServicePriceEntry("provtryckning_strang", "Sträng", "st", Decimal("500")),),
    )
    offer = price_pressure_test_offer(_QUANTITIES, book)
    assert offer["totals"]["itemised_total"] == "22500.00"
    assert offer["price_book_id"] == "egen"
