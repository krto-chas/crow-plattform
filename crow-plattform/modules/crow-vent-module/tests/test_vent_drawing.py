from __future__ import annotations

import os
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest

from crow_vent_drawing import (
    assess_drawing_text,
    extract_apartments,
    extract_levels,
    parse_drawing_number,
    point_distance_m,
)

_PLAN_TEXT = (
    "TRAPPHUS 3 11,9 m2 43-1101 4 RoKA: 87,8 m2 SOV 17,6 m2 "
    "43-1102 2 RoKA: 42,6 m2 VARDAGSRUM/KÖK 23,9 m2 "
    "43-1103 4 RoKA: 106,4 m2 +21,08"
)

_FORRAD_TEXT = "FÖRRÅD 41-1101 3 RoK A: 4,0 m2 41-1102 3 RoK A: 4,2 m2 +14,65"


def test_parse_drawing_number_extracts_plan_and_part() -> None:
    ref = parse_drawing_number("V-57-1-41103")
    assert ref is not None
    assert (ref.series, ref.plan, ref.part) == ("4", "11", "03")
    assert parse_drawing_number("V-57-Besk") is None


def test_extracts_apartments_with_authoritative_area_on_own_plan() -> None:
    records = extract_apartments(_PLAN_TEXT, "V-57-1-41103")
    by_id = {record.apartment_id: record for record in records}
    assert set(by_id) == {"43-1101", "43-1102", "43-1103"}
    assert by_id["43-1101"].rok == 4
    assert by_id["43-1101"].area_m2 == Decimal("87.8")
    assert by_id["43-1101"].area_is_authoritative
    assert all(record.stairwell_id == "trh-3" for record in records)


def test_apartment_list_on_other_plan_gives_no_authoritative_area() -> None:
    records = extract_apartments(_FORRAD_TEXT, "V-57-1-40901")
    by_id = {record.apartment_id: record for record in records}
    assert set(by_id) == {"41-1101", "41-1102"}
    forrad = by_id["41-1101"]
    assert forrad.plan == "11"
    assert forrad.area_m2 is None
    assert not forrad.area_is_authoritative
    assert forrad.rok == 3


def test_levels_are_deduplicated_and_sorted() -> None:
    levels = extract_levels("+21,08 text +14,65 mer +21,08", "V-57-1-41101")
    assert [item.elevation_m for item in levels] == [Decimal("14.65"), Decimal("21.08")]


def test_assessment_flags_empty_residential_plan() -> None:
    assessment = assess_drawing_text("bara stämpeltext", "V-57-1-41104", "text_available")
    assert assessment.needs_raster_review
    assert assessment.apartment_label_count == 0
    assert assessment.notes


def test_assessment_accepts_plan_with_apartments() -> None:
    assessment = assess_drawing_text(_PLAN_TEXT, "V-57-1-41103", "text_available")
    assert not assessment.needs_raster_review
    assert assessment.apartment_label_count == 3


def test_point_distance_at_scale_1_50() -> None:
    distance = point_distance_m((0.0, 0.0), (56.69291338582678, 0.0), 50)
    assert distance == Decimal("1.00")
    with pytest.raises(ValueError):
        point_distance_m((0.0, 0.0), (1.0, 0.0), 0)


def test_real_drawings_yield_expected_stairwell_counts() -> None:
    drawings_dir = os.environ.get("CROW_BERGHALLEN_DRAWINGS")
    if not drawings_dir:
        pytest.skip("CROW_BERGHALLEN_DRAWINGS not set; customer files stay outside the repo")
    from crow_pdf_evidence import PdfEvidenceExtractor

    extractor = PdfEvidenceExtractor()
    counts: Counter[str] = Counter()
    seen: set[str] = set()
    for path in sorted(Path(drawings_dir).glob("V-57-1-*.pdf")):
        page = extractor.extract_path(path).pages[0]
        for record in extract_apartments(page.text, path.stem):
            if record.apartment_id not in seen:
                seen.add(record.apartment_id)
                counts[record.stairwell_id] += 1
    assert dict(counts) == {
        "trh-1": 8,
        "trh-2": 7,
        "trh-3": 10,
        "trh-4": 10,
        "radhus": 3,
    }
