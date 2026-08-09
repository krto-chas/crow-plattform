import pytest

from crow_takeoff_consolidation import (
    PriceBook,
    PriceBookEntry,
    consolidate_takeoffs,
    price_consolidated_takeoff,
    takeoff_from_geometry,
    takeoff_from_table,
)
from crow_vent.lexicon import VentLexicon


def build_consolidated() -> dict:
    geometry = takeoff_from_geometry(
        {
            "lines": [
                {
                    "component_code": "T",
                    "component_name": "Tilluftskanal",
                    "dimension": "Ø125",
                    "quantity": 14,
                    "length_m": 118.0,
                    "system_ids": ["LB01"],
                },
                {
                    "component_code": "TD",
                    "component_name": "Tilluftsdon",
                    "dimension": "Ej angiven",
                    "quantity": 24,
                    "length_m": None,
                    "system_ids": ["LB01"],
                },
                {
                    "component_code": "SP",
                    "component_name": "Spjäll",
                    "dimension": "Ej angiven",
                    "quantity": 6,
                    "length_m": None,
                    "system_ids": ["LB01"],
                },
            ]
        },
        source_id="dxf:V-57-1-01",
    )
    table = takeoff_from_table(
        [["T-125", "132", "m"]],
        source_id="xlsx:mangd",
        lexicon=VentLexicon.default(),
    )
    return consolidate_takeoffs([geometry, table])


def price_book() -> PriceBook:
    return PriceBook(
        price_book_id="prisbok-vent-2026",
        currency="SEK",
        labour_rate_per_hour=520.0,
        entries=(
            PriceBookEntry("duct", "T", "Ø125", "m", 89.0, 0.35),
            PriceBookEntry("component", "TD", "*", "st", 640.0, 0.5),
        ),
    )


def test_pricing_totals_and_exclusions() -> None:
    result = price_consolidated_takeoff(build_consolidated(), price_book())

    assert result["schema_version"].startswith("crow-takeoff-pricing")
    # TD: corroborated 24 st -> priced; T Ø125 discrepant -> reservation; SP -> unpriced
    assert result["priced_line_count"] == 1
    assert result["reservation_count"] == 1
    assert result["unpriced_line_count"] == 1

    td = result["lines"][0]
    assert td["code"] == "TD"
    assert td["material_amount"] == 24 * 640.0
    assert td["labour_hours"] == 12.0
    assert td["labour_amount"] == 12.0 * 520.0
    assert result["grand_total"] == td["line_total"]
    assert result["labour_hours_total"] == 12.0

    assert result["reservations"][0]["code"] == "T"
    assert result["reservations"][0]["reason"] == "unresolved_quantity"
    assert result["unpriced"][0]["code"] == "SP"
    assert result["unpriced"][0]["reason"] == "no_price_entry"
    assert len(result["client_questions"]) == 1


def test_wildcard_dimension_and_unit_guard() -> None:
    consolidated = build_consolidated()
    book = PriceBook(
        price_book_id="pb",
        labour_rate_per_hour=500.0,
        entries=(PriceBookEntry("component", "TD", "*", "m", 640.0),),
    )
    result = price_consolidated_takeoff(consolidated, book)
    assert result["priced_line_count"] == 0
    assert any(item["reason"] == "price_unit_mismatch" for item in result["unpriced"])


def test_wrong_schema_is_rejected() -> None:
    with pytest.raises(ValueError):
        price_consolidated_takeoff({"schema_version": "other"}, price_book())


def test_determinism() -> None:
    first = price_consolidated_takeoff(build_consolidated(), price_book())
    second = price_consolidated_takeoff(build_consolidated(), price_book())
    assert first == second
