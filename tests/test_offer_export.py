from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

# ruff: noqa: E402  (importskip måste ske före modulimporterna)
from crow_offer_export import write_offer_workbook, write_protocol_workbook
from crow_pressure_test import (
    OfferItemRequest,
    TightnessClass,
    default_service_price_book,
    load_knowledge,
    price_pressure_test_offer,
)
from crow_riser_model import (
    LevelTable,
    RiserConfiguration,
    build_riser_model,
    pressure_test_service_quantities,
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


def _service_quantities() -> dict[str, object]:
    levels = LevelTable.from_pairs({"10": "17.27", "11": "21.08", "14": "29.58"})
    result = build_riser_model(
        [
            _apartment("41-1001", "trh-1", "10"),
            _apartment("41-1101", "trh-1", "11"),
            _apartment("42-1001", "trh-2", "10"),
        ],
        levels,
        RiserConfiguration(top_plan="14"),
    )
    return pressure_test_service_quantities(result)


def test_offer_workbook_roundtrip(tmp_path: Path) -> None:
    quantities = _service_quantities()
    offer = price_pressure_test_offer(
        quantities,
        default_service_price_book(),
        [OfferItemRequest("samlingslada", Decimal(2)), OfferItemRequest("okand", Decimal(1))],
        establishments=3,
    )
    path = write_offer_workbook(offer, quantities, tmp_path / "offert.xlsx", "Testprojekt")
    workbook = openpyxl.load_workbook(path)
    assert set(workbook.sheetnames) == {"Sammanställning", "trh-1", "trh-2"}
    summary = workbook["Sammanställning"]
    texts = [cell.value for row in summary.iter_rows() for cell in row if cell.value]
    assert any("REKOMMENDERAT FAST PRIS" in str(value) for value in texts)
    assert any("RESERVATION: okand" in str(value) for value in texts)
    stairwell_sheet = workbook["trh-1"]
    values = {cell.value for row in stairwell_sheet.iter_rows() for cell in row}
    assert 6 in values  # 2 lgh × 3 strängar


def test_offer_workbook_amounts_match_payload(tmp_path: Path) -> None:
    quantities = _service_quantities()
    offer = price_pressure_test_offer(quantities, default_service_price_book())
    path = write_offer_workbook(offer, quantities, tmp_path / "offert.xlsx", "Testprojekt")
    summary = openpyxl.load_workbook(path)["Sammanställning"]
    total = float(offer["totals"]["itemised_total"])
    cells = [cell.value for row in summary.iter_rows() for cell in row]
    assert total in cells


def test_protocol_workbook_uses_knowledge_factors(tmp_path: Path) -> None:
    knowledge = load_knowledge()
    path = write_protocol_workbook(
        knowledge, tmp_path / "protokoll.xlsx", "Testprojekt", TightnessClass.C
    )
    workbook = openpyxl.load_workbook(path)
    assert workbook.sheetnames[0] == "Protokoll"
    requirements = workbook["Krav & standarder"]
    rows = {
        row[0].value: row
        for row in requirements.iter_rows(min_row=4, max_row=7)
        if row[0].value
    }
    assert rows["C"][1].value == pytest.approx(0.003)
    assert rows["C"][2].value == pytest.approx(0.147387, abs=1e-6)
    assert rows["C"][4].value == "PROJEKTKRAV"
    protocol = workbook["Protokoll"]
    formulas = [
        cell.value
        for row in protocol.iter_rows()
        for cell in row
        if isinstance(cell.value, str) and cell.value.startswith("=")
    ]
    assert any("VLOOKUP" in formula and "^0.65" in formula for formula in formulas)
    standard_texts = [
        cell.value for row in requirements.iter_rows() for cell in row if cell.value
    ]
    assert any("SS-EN 1507" in str(value) for value in standard_texts)
