from __future__ import annotations

from decimal import Decimal

import pytest

from crow_ovk_pricing import (
    SCHEMA_VERSION,
    BuildingCategory,
    InspectionType,
    OvkObjectPart,
    OvkQuoteRequest,
    PricingBasis,
    VentilationSystemType,
    build_quote,
    load_taxa,
    quote_to_payload,
)


def _single(part: OvkObjectPart, inspection_type: InspectionType) -> OvkQuoteRequest:
    return OvkQuoteRequest(inspection_type=inspection_type, parts=(part,))


def test_flerbostadshus_prices_per_apartment() -> None:
    taxa = load_taxa()
    quote = build_quote(
        _single(OvkObjectPart(category=BuildingCategory.FLERBOSTADSHUS, apartment_count=33, system_type=VentilationSystemType.F), InspectionType.ATERKOMMANDE), taxa)
    line = quote.lines[0]
    assert line.pricing_basis is PricingBasis.PER_APARTMENT
    assert line.quantity == Decimal(33)
    assert line.unit == "lgh"
    assert line.amount == Decimal(33) * taxa.rate(BuildingCategory.FLERBOSTADSHUS, InspectionType.ATERKOMMANDE)
    assert quote.total == quote.base_fee + quote.subtotal
    assert not quote.minimum_applied


def test_flerbostadshus_requires_apartment_count() -> None:
    taxa = load_taxa()
    with pytest.raises(ValueError, match="apartment_count is required"):
        build_quote(_single(OvkObjectPart(category=BuildingCategory.FLERBOSTADSHUS), InspectionType.ATERKOMMANDE), taxa)


def test_smahus_flat_price_ignores_optional_size() -> None:
    taxa = load_taxa()
    with_size = build_quote(_single(OvkObjectPart(category=BuildingCategory.SMAHUS, area_m2=Decimal("145")), InspectionType.FORSTAGANG), taxa)
    without_size = build_quote(_single(OvkObjectPart(category=BuildingCategory.SMAHUS), InspectionType.FORSTAGANG), taxa)
    assert with_size.total == without_size.total
    assert with_size.lines[0].pricing_basis is PricingBasis.FLAT_PER_UNIT


def test_smahus_two_units() -> None:
    taxa = load_taxa()
    quote = build_quote(_single(OvkObjectPart(category=BuildingCategory.SMAHUS, unit_count=2), InspectionType.FORSTAGANG), taxa)
    rate = taxa.rate(BuildingCategory.SMAHUS, InspectionType.FORSTAGANG)
    assert quote.subtotal == Decimal(2) * rate


def test_smahus_rejects_recurring_inspection() -> None:
    taxa = load_taxa()
    with pytest.raises(ValueError, match="förstagångsbesiktning"):
        build_quote(_single(OvkObjectPart(category=BuildingCategory.SMAHUS), InspectionType.ATERKOMMANDE), taxa)


def test_hotell_prices_per_room() -> None:
    taxa = load_taxa()
    quote = build_quote(_single(OvkObjectPart(category=BuildingCategory.HOTELL, room_count=120, system_type=VentilationSystemType.FTX), InspectionType.ATERKOMMANDE), taxa)
    line = quote.lines[0]
    assert line.pricing_basis is PricingBasis.PER_ROOM
    assert line.quantity == Decimal(120)
    assert line.unit == "rum"
    assert line.amount == Decimal(120) * taxa.rate(BuildingCategory.HOTELL, InspectionType.ATERKOMMANDE)
    assert line.recurring_interval_years == 3


def test_hotell_requires_room_count() -> None:
    taxa = load_taxa()
    with pytest.raises(ValueError, match="room_count is required"):
        build_quote(_single(OvkObjectPart(category=BuildingCategory.HOTELL), InspectionType.FORSTAGANG), taxa)
    with pytest.raises(ValueError, match="room_count must be >= 1"):
        build_quote(_single(OvkObjectPart(category=BuildingCategory.HOTELL, room_count=0), InspectionType.FORSTAGANG), taxa)


def test_lokal_prices_per_area_and_system_type() -> None:
    taxa = load_taxa()
    ftx = build_quote(_single(OvkObjectPart(category=BuildingCategory.LOKAL, system_type=VentilationSystemType.FTX, area_m2=Decimal("2400")), InspectionType.ATERKOMMANDE), taxa)
    s = build_quote(_single(OvkObjectPart(category=BuildingCategory.LOKAL, system_type=VentilationSystemType.S, area_m2=Decimal("2400")), InspectionType.ATERKOMMANDE), taxa)
    assert ftx.lines[0].pricing_basis is PricingBasis.PER_AREA
    assert ftx.lines[0].unit == "m2"
    assert ftx.subtotal > s.subtotal


def test_lokal_requires_area_and_system_type() -> None:
    taxa = load_taxa()
    with pytest.raises(ValueError, match="area_m2 is required"):
        build_quote(_single(OvkObjectPart(category=BuildingCategory.LOKAL, system_type=VentilationSystemType.FTX), InspectionType.FORSTAGANG), taxa)
    with pytest.raises(ValueError, match="system_type is required"):
        build_quote(_single(OvkObjectPart(category=BuildingCategory.LOKAL, area_m2=Decimal("500")), InspectionType.FORSTAGANG), taxa)


def test_combined_hotel_with_restaurant_part() -> None:
    taxa = load_taxa()
    quote = build_quote(OvkQuoteRequest(inspection_type=InspectionType.ATERKOMMANDE, parts=(OvkObjectPart(category=BuildingCategory.HOTELL, room_count=80, system_type=VentilationSystemType.FTX), OvkObjectPart(category=BuildingCategory.LOKAL, system_type=VentilationSystemType.FTX, area_m2=Decimal("650"), label="Restaurang och konferens"))), taxa)
    assert len(quote.lines) == 2
    assert quote.lines[1].description.endswith("Restaurang och konferens")
    assert quote.subtotal == quote.lines[0].amount + quote.lines[1].amount
    assert quote.total == quote.base_fee + quote.subtotal
    assert quote.next_inspection_interval_years == 3


def test_combined_quote_uses_shortest_known_interval() -> None:
    taxa = load_taxa()
    quote = build_quote(OvkQuoteRequest(inspection_type=InspectionType.ATERKOMMANDE, parts=(OvkObjectPart(category=BuildingCategory.FLERBOSTADSHUS, apartment_count=24, system_type=VentilationSystemType.F), OvkObjectPart(category=BuildingCategory.LOKAL, system_type=VentilationSystemType.FTX, area_m2=Decimal("300"), label="Butik i bottenplan"))), taxa)
    assert quote.lines[0].recurring_interval_years == 6
    assert quote.lines[1].recurring_interval_years == 3
    assert quote.next_inspection_interval_years == 3


def test_empty_request_is_rejected() -> None:
    taxa = load_taxa()
    with pytest.raises(ValueError, match="at least one object part"):
        build_quote(OvkQuoteRequest(inspection_type=InspectionType.FORSTAGANG), taxa)


def test_smahus_part_rejected_in_combined_recurring_request() -> None:
    taxa = load_taxa()
    with pytest.raises(ValueError, match="förstagångsbesiktning"):
        build_quote(OvkQuoteRequest(inspection_type=InspectionType.ATERKOMMANDE, parts=(OvkObjectPart(category=BuildingCategory.LOKAL, system_type=VentilationSystemType.F, area_m2=Decimal("400")), OvkObjectPart(category=BuildingCategory.SMAHUS))), taxa)


def test_minimum_charge_applies_to_small_objects() -> None:
    taxa = load_taxa()
    quote = build_quote(_single(OvkObjectPart(category=BuildingCategory.LOKAL, system_type=VentilationSystemType.S, area_m2=Decimal("80")), InspectionType.ATERKOMMANDE), taxa)
    assert quote.minimum_applied
    assert quote.total == taxa.minimum_total
    assert quote.total > quote.base_fee + quote.subtotal


def test_base_fee_always_included_above_minimum() -> None:
    taxa = load_taxa()
    quote = build_quote(_single(OvkObjectPart(category=BuildingCategory.FLERBOSTADSHUS, apartment_count=100), InspectionType.FORSTAGANG), taxa)
    assert not quote.minimum_applied
    assert quote.total == quote.base_fee + quote.subtotal
    assert quote.base_fee == taxa.base_fee


def test_recurring_intervals_follow_bfs_2011_16() -> None:
    taxa = load_taxa()
    assert taxa.recurring_interval_years(BuildingCategory.FLERBOSTADSHUS, VentilationSystemType.FTX) == 3
    assert taxa.recurring_interval_years(BuildingCategory.FLERBOSTADSHUS, VentilationSystemType.F) == 6
    assert taxa.recurring_interval_years(BuildingCategory.LOKAL, VentilationSystemType.F, school_or_care=True) == 3
    assert taxa.recurring_interval_years(BuildingCategory.SMAHUS, VentilationSystemType.FTX) is None
    assert taxa.recurring_interval_years(BuildingCategory.FLERBOSTADSHUS, None) is None


def test_quote_is_deterministic() -> None:
    taxa = load_taxa()
    request = OvkQuoteRequest(inspection_type=InspectionType.FORSTAGANG, parts=(OvkObjectPart(category=BuildingCategory.LOKAL, system_type=VentilationSystemType.FTX, area_m2=Decimal("3150.5")),))
    assert build_quote(request, taxa) == build_quote(request, taxa)


def test_payload_serialises_money_as_strings() -> None:
    taxa = load_taxa()
    quote = build_quote(_single(OvkObjectPart(category=BuildingCategory.FLERBOSTADSHUS, apartment_count=12), InspectionType.ATERKOMMANDE), taxa)
    payload = quote_to_payload(quote)
    assert payload["schema_version"] == SCHEMA_VERSION
    assert isinstance(payload["total"], str)
    assert isinstance(payload["lines"][0]["unit_price"], str)
    assert Decimal(payload["total"]) == quote.total


def test_lexicon_covers_all_system_types_for_lokal() -> None:
    taxa = load_taxa()
    for system in VentilationSystemType:
        for inspection in InspectionType:
            rate = taxa.rate(BuildingCategory.LOKAL, inspection, system)
            assert rate > 0


def test_negative_sizes_are_rejected() -> None:
    taxa = load_taxa()
    with pytest.raises(ValueError, match="apartment_count must be >= 1"):
        build_quote(_single(OvkObjectPart(category=BuildingCategory.FLERBOSTADSHUS, apartment_count=0), InspectionType.ATERKOMMANDE), taxa)
    with pytest.raises(ValueError, match="area_m2 must be positive"):
        build_quote(_single(OvkObjectPart(category=BuildingCategory.LOKAL, system_type=VentilationSystemType.F, area_m2=Decimal("-10")), InspectionType.ATERKOMMANDE), taxa)
