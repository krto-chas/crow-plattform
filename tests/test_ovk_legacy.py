from io import BytesIO

from crow_ovk_legacy import LegacySourceKind, preview_legacy_file
from openpyxl import Workbook
from pypdf import PdfWriter


def _xlsx_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "OVK"
    sheet.append(["Besiktning 2024-05-17", "System FTX01"])
    sheet.append(["Lgh 1203", "uppmätt 34,5 l/s", "projekterat 40 l/s"])
    sheet.append(["Anmärkning: Smutsigt frånluftsdon"])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_xlsx_preview_extracts_explicit_facts_with_cell_provenance() -> None:
    preview = preview_legacy_file("project-1", "ovk-2024.xlsx", _xlsx_bytes())

    assert preview.kind is LegacySourceKind.XLSX
    values = {(fact.field, fact.value) for fact in preview.facts}
    assert ("inspection_date", "2024-05-17") in values
    assert ("system_id", "FTX01") in values
    assert ("apartment_number", "1203") in values
    assert ("measured_airflow", "34.5 l/s") in values
    assert ("designed_airflow", "40 l/s") in values
    assert ("finding", "Smutsigt frånluftsdon") in values
    assert all(fact.source.locator.startswith("sheet:OVK:cells:") for fact in preview.facts)


def test_unlabelled_airflow_is_sent_to_review() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["FTX01", "B1", "34 l/s", "40 l/s"])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()

    preview = preview_legacy_file("project-1", "old.xlsx", buffer.getvalue())

    assert any(item.reason == "unlabelled_airflow_value" for item in preview.review)
    assert preview.ready_for_commit is False


def test_pdf_reader_accepts_pdf_and_preserves_source_hash() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buffer = BytesIO()
    writer.write(buffer)

    preview = preview_legacy_file("project-1", "old.pdf", buffer.getvalue())

    assert preview.kind is LegacySourceKind.PDF
    assert len(preview.source_sha256) == 64
    assert preview.facts == ()


def test_unsupported_format_is_rejected() -> None:
    try:
        preview_legacy_file("project-1", "old.xls", b"legacy")
    except ValueError as exc:
        assert "Unsupported legacy OVK file type" in str(exc)
    else:
        raise AssertionError("legacy .xls must not be silently accepted")
