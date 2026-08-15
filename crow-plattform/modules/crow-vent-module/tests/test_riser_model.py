from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest

from crow_riser_model import (
    LevelTable,
    RiserConfiguration,
    build_riser_model,
    pressure_test_service_quantities,
    to_source_takeoff,
)
from crow_vent_drawing import ApartmentRecord


def _apartment(apartment_id: str, stairwell: str, plan: str) -> ApartmentRecord:
    return ApartmentRecord(
        apartment_id=apartment_id,
        stairwell_id=stairwell,
        plan=plan,
        rok=None,
        area_m2=None,
        area_is_authoritative=False,
        source_document="test",
    )


_LEVELS = LevelTable.from_pairs({"10": "17.27", "11": "21.08", "14": "29.58"})
_CONFIG = RiserConfiguration(top_plan="14")


def test_builds_three_strings_per_apartment_with_height_plus_allowance() -> None:
    result = build_riser_model([_apartment("41-1001", "trh-1", "10")], _LEVELS, _CONFIG)
    assert result.string_count == 3
    assert {item.kind for item in result.strings} == {"tilluft", "franluft", "imkanal"}
    assert all(item.length_m == Decimal("13.31") for item in result.strings)
    assert result.summaries[0].apartment_count == 1


def test_missing_level_is_skipped_with_reason_not_silently() -> None:
    result = build_riser_model([_apartment("43-1201", "trh-3", "12")], _LEVELS, _CONFIG)
    assert result.string_count == 0
    assert result.skipped[0]["reason"] == "missing_or_inverted_level"
    assert result.skipped[0]["apartment_id"] == "43-1201"


def test_duplicate_apartment_ids_counted_once() -> None:
    result = build_riser_model(
        [_apartment("41-1001", "trh-1", "10"), _apartment("41-1001", "trh-1", "10")],
        _LEVELS,
        _CONFIG,
    )
    assert result.string_count == 3


def test_source_takeoff_groups_by_medium_and_dimension() -> None:
    result = build_riser_model(
        [_apartment("41-1001", "trh-1", "10"), _apartment("41-1101", "trh-1", "11")],
        _LEVELS,
        _CONFIG,
    )
    takeoff = to_source_takeoff(result, _CONFIG, "riser-berghallen")
    by_code = {line.code: line for line in takeoff.lines}
    assert set(by_code) == {"T1", "F1", "IM1"}
    assert by_code["T1"].dimension == "Ø160"
    assert by_code["T1"].unit == "m"
    assert by_code["T1"].quantity == pytest.approx(13.31 + 9.50)
    assert by_code["T1"].evidence["string_count"] == 2


def test_service_quantities_round_partial_scope_up() -> None:
    apartments = [_apartment(f"41-10{i:02d}", "trh-1", "10") for i in range(1, 4)]
    result = build_riser_model(apartments, _LEVELS, _CONFIG)
    payload = pressure_test_service_quantities(result, {"schakt": 50})
    assert payload["totals"]["string_count"] == 9
    assert payload["totals"]["strings_to_test"] == 5  # ceil(9 * 0.5)
    with pytest.raises(ValueError):
        pressure_test_service_quantities(result, {"schakt": 0})


def test_full_scope_matches_string_count() -> None:
    apartments = [_apartment("41-1001", "trh-1", "10"), _apartment("42-1001", "trh-2", "10")]
    result = build_riser_model(apartments, _LEVELS, _CONFIG)
    payload = pressure_test_service_quantities(result)
    assert payload["totals"]["strings_to_test"] == payload["totals"]["string_count"] == 6


def test_real_berghallen_riser_model_matches_expected_totals() -> None:
    drawings_dir = os.environ.get("CROW_BERGHALLEN_DRAWINGS")
    if not drawings_dir:
        pytest.skip("CROW_BERGHALLEN_DRAWINGS not set; customer files stay outside the repo")
    from crow_pdf_evidence import PdfEvidenceExtractor
    from crow_vent_drawing import extract_apartments

    extractor = PdfEvidenceExtractor()
    seen: dict[str, ApartmentRecord] = {}
    for path in sorted(Path(drawings_dir).glob("V-57-1-*.pdf")):
        page = extractor.extract_path(path).pages[0]
        for record in extract_apartments(page.text, path.stem):
            seen.setdefault(record.apartment_id, record)
    levels = LevelTable.from_pairs(
        {"10": "17.27", "11": "21.08", "12": "23.91", "13": "26.74", "14": "29.58"}
    )
    hus_cd = [item for item in seen.values() if item.stairwell_id != "radhus"]
    result = build_riser_model(hus_cd, levels, RiserConfiguration(top_plan="14"))
    assert result.string_count == 105  # 35 lgh × 3 strängar
    by_stairwell = {item.stairwell_id: item for item in result.summaries}
    expected_lengths = {
        "trh-1": Decimal("200"),
        "trh-2": Decimal("188"),
        "trh-3": Decimal("248"),
        "trh-4": Decimal("248"),
    }
    for stairwell, expected in expected_lengths.items():
        actual = by_stairwell[stairwell].total_length_m
        assert abs(actual - expected) / expected < Decimal("0.05"), (stairwell, actual)
    radhus = [item for item in seen.values() if item.stairwell_id == "radhus"]
    radhus_result = build_riser_model(radhus, levels, RiserConfiguration(top_plan="12"))
    assert radhus_result.string_count == 9
    assert abs(radhus_result.total_length_m - Decimal("63")) / Decimal("63") < Decimal("0.2")
