"""PDF-rendering av OVK-protokoll och OVK-intyg (fpdf2, latin-1-säker svenska)."""

from __future__ import annotations

from fpdf import FPDF

from crow_ovk import CheckStatus, FindingSeverity, InspectionConclusion
from crow_ovk_intyg import IntygResult, OvkIntyg
from crow_ovk_workflow import AggregatStatus, FastighetsnivaStatus, OvkWorkflowRecord

_CHECK_LABELS = {
    CheckStatus.PASS: "Godkänd",
    CheckStatus.FAIL: "Underkänd",
    CheckStatus.NOT_CHECKED: "Ej kontrollerad",
    CheckStatus.NOT_APPLICABLE: "Ej tillämplig",
}

_SEVERITY_LABELS = {
    FindingSeverity.INFO: "Info",
    FindingSeverity.MINOR: "Mindre",
    FindingSeverity.MAJOR: "Allvarlig",
}

_CONCLUSION_LABELS = {
    InspectionConclusion.APPROVED: "GODKÄND",
    InspectionConclusion.DEFICIENCIES: "EJ GODKÄND - BRISTER",
    InspectionConclusion.PENDING: "EJ AVSLUTAD",
}

_AGGREGAT_LABELS = {
    AggregatStatus.BESIKTIGAD: "Besiktigad",
    AggregatStatus.EJ_BESIKTIGAD: "EJ BESIKTIGAD",
    AggregatStatus.EJ_TILLAMPLIG: "Ej tillämplig",
}

_FASTIGHETSNIVA_LABELS = {
    FastighetsnivaStatus.SAMTLIGA_BESIKTADE: "Samtliga system i fastigheten besiktigade",
    FastighetsnivaStatus.DELVIS_BESIKTADE: "DELVIS BESIKTIGADE - delbesiktning",
    FastighetsnivaStatus.SYSTEMFORTECKNING_EJ_BEKRAFTAD: ("Systemförteckningen ej bekräftad"),
}

_RESULT_LABELS = {
    IntygResult.GODKAND: "GODKÄND",
    IntygResult.EJ_GODKAND: "EJ GODKÄND",
}

_TYPE_LABELS = {
    "forstagang": "Förstagångsbesiktning",
    "aterkommande": "Återkommande besiktning",
}


class _CrowPdf(FPDF):
    def __init__(self, footer_text: str) -> None:
        super().__init__(format="A4")
        self._footer_text = footer_text
        self.set_auto_page_break(auto=True, margin=18)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("helvetica", size=8)
        self.set_text_color(96, 106, 116)
        self.cell(0, 6, self._footer_text, align="C")


def _title(pdf: FPDF, text: str) -> None:
    pdf.set_font("helvetica", style="B", size=20)
    pdf.set_text_color(24, 33, 43)
    pdf.cell(0, 12, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _heading(pdf: FPDF, text: str) -> None:
    pdf.ln(3)
    pdf.set_font("helvetica", style="B", size=12)
    pdf.set_text_color(24, 33, 43)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")


def _kv(pdf: FPDF, key: str, value: str) -> None:
    pdf.set_font("helvetica", style="B", size=10)
    pdf.cell(58, 7, key, border=1)
    pdf.set_font("helvetica", size=10)
    pdf.multi_cell(0, 7, value, border=1, new_x="LMARGIN", new_y="NEXT")


def _table_header(pdf: FPDF, columns: tuple[tuple[str, int], ...]) -> None:
    pdf.set_font("helvetica", style="B", size=9)
    pdf.set_fill_color(238, 242, 245)
    for label, width in columns:
        pdf.cell(width, 7, label, border=1, fill=True)
    pdf.ln()


def _table_row(pdf: FPDF, cells: tuple[tuple[str, int], ...]) -> None:
    pdf.set_font("helvetica", size=9)
    for text, width in cells:
        pdf.cell(width, 7, text, border=1)
    pdf.ln()


def _result_banner(pdf: FPDF, label: str, *, positive: bool) -> None:
    pdf.ln(4)
    pdf.set_font("helvetica", style="B", size=18)
    if positive:
        pdf.set_fill_color(229, 246, 234)
        pdf.set_text_color(28, 107, 52)
    else:
        pdf.set_fill_color(251, 233, 233)
        pdf.set_text_color(143, 32, 32)
    pdf.cell(0, 14, label, border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(24, 33, 43)


def protocol_pdf(record: OvkWorkflowRecord) -> bytes:
    inspection = record.inspection
    pdf = _CrowPdf(f"OVK-protokoll · Besiktnings-ID {inspection.inspection_id} · Crow-plattformen")
    pdf.add_page()
    _title(pdf, "OVK-PROTOKOLL")
    _kv(pdf, "Byggnad", f"{inspection.ovk_object.name} ({inspection.ovk_object.building_id})")
    _kv(pdf, "Adress", inspection.ovk_object.address or "-")
    _kv(pdf, "Projekt", inspection.ovk_object.project_id)
    _kv(pdf, "Besiktnings-ID", inspection.inspection_id)

    _heading(pdf, "Ventilationssystem")
    _table_header(pdf, (("System", 35), ("Typ", 25), ("Benämning", 130)))
    for system in inspection.systems:
        _table_row(pdf, ((system.system_id, 35), (system.system_type, 25), (system.label, 130)))

    _heading(pdf, "Kontrollpunkter")
    _table_header(pdf, (("Punkt", 60), ("System", 30), ("Status", 40), ("Notering", 60)))
    for checkpoint in inspection.checkpoints:
        _table_row(
            pdf,
            (
                (checkpoint.label, 60),
                (checkpoint.system_id or "-", 30),
                (_CHECK_LABELS[checkpoint.status], 40),
                (checkpoint.note or "-", 60),
            ),
        )

    _heading(pdf, "Anmärkningar")
    if inspection.findings:
        _table_header(pdf, (("ID", 20), ("Beskrivning", 90), ("Allvar", 30), ("Åtgärd krävs", 50)))
        for finding in inspection.findings:
            _table_row(
                pdf,
                (
                    (finding.finding_id, 20),
                    (finding.description, 90),
                    (_SEVERITY_LABELS[finding.severity], 30),
                    ("Ja" if finding.action_required else "Nej", 50),
                ),
            )
    else:
        pdf.set_font("helvetica", size=10)
        pdf.cell(0, 7, "Inga anmärkningar.", new_x="LMARGIN", new_y="NEXT")

    _heading(pdf, "Besiktningstäckning - fläktar/aggregat")
    if record.coverage is not None and record.coverage.aggregat:
        _table_header(pdf, (("Aggregat", 40), ("Status", 45), ("Motivering (STATED)", 105)))
        for item in record.coverage.aggregat:
            note = (
                f"{item.justification} - {item.stated_by}"
                if item.status is AggregatStatus.EJ_BESIKTIGAD
                else "-"
            )
            _table_row(pdf, ((item.label, 40), (_AGGREGAT_LABELS[item.status], 45), (note, 105)))
        _kv(pdf, "Fastighetsnivå", _FASTIGHETSNIVA_LABELS[record.coverage.fastighetsniva])
    else:
        pdf.set_font("helvetica", size=10)
        pdf.cell(
            0,
            7,
            "Täckning saknas - protokollet kan inte färdigställas.",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    _result_banner(
        pdf,
        _CONCLUSION_LABELS[inspection.conclusion],
        positive=inspection.conclusion is InspectionConclusion.APPROVED,
    )
    return bytes(pdf.output())


def intyg_pdf(intyg: OvkIntyg) -> bytes:
    pdf = _CrowPdf(f"OVK-intyg · Intygs-ID {intyg.intyg_id} · Crow-plattformen")
    pdf.add_page()
    _title(pdf, "OVK-INTYG")
    pdf.set_font("helvetica", size=10)
    pdf.multi_cell(
        0,
        6,
        "Intyg över obligatorisk ventilationskontroll enligt plan- och bygglagstiftningen.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)
    _kv(pdf, "Fastighetsbeteckning", intyg.fastighetsbeteckning)
    _kv(pdf, "Byggnad", f"{intyg.object_name} ({intyg.building_id})")
    _kv(pdf, "Adress", intyg.address or "-")
    _kv(pdf, "Byggnadens ägare", intyg.byggnadsagare.name)
    _kv(
        pdf,
        "Besiktningstyp",
        _TYPE_LABELS.get(intyg.inspection_type.value, intyg.inspection_type.value),
    )
    _kv(pdf, "Besiktningsdatum", intyg.inspection_date.isoformat())

    _heading(pdf, "Funktionskontrollant")
    kontrollant = intyg.funktionskontrollant
    _kv(pdf, "Namn", kontrollant.name)
    _kv(pdf, "Behörighet", kontrollant.behorighet.value)
    _kv(pdf, "Certifieringsorgan", kontrollant.certification_body)
    _kv(pdf, "Certifikatnummer", kontrollant.certificate_number)
    _kv(
        pdf,
        "Certifikat giltigt t.o.m.",
        kontrollant.certificate_valid_to.isoformat()
        if kontrollant.certificate_valid_to is not None
        else "-",
    )

    _heading(pdf, "Omfattade ventilationssystem")
    _table_header(pdf, (("System", 35), ("Typ", 25), ("Benämning", 90), ("Resultat", 40)))
    for system in intyg.systems:
        _table_row(
            pdf,
            (
                (system.system_id, 35),
                (system.system_type, 25),
                (system.label, 90),
                (_RESULT_LABELS[system.result], 40),
            ),
        )

    _result_banner(
        pdf,
        _RESULT_LABELS[intyg.result],
        positive=intyg.result is IntygResult.GODKAND,
    )

    _heading(pdf, "Besiktningsomfattning")
    _kv(pdf, "Fastighetsnivå", _FASTIGHETSNIVA_LABELS[intyg.fastighetsniva])
    if intyg.delbesiktning:
        pdf.set_font("helvetica", style="B", size=10)
        pdf.set_text_color(146, 64, 14)
        pdf.cell(
            0,
            7,
            "DELBESIKTNING - delar av systemet har inte besiktigats.",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_text_color(24, 33, 43)
        _table_header(pdf, (("Aggregat", 40), ("Motivering (STATED)", 110), ("Angiven av", 40)))
        for item in intyg.uninspected_aggregat:
            _table_row(
                pdf,
                ((item.label, 40), (item.justification, 110), (item.stated_by, 40)),
            )

    _heading(pdf, "Nästa besiktning")
    _kv(
        pdf,
        "Senast",
        intyg.next_inspection.due_date.isoformat()
        if intyg.next_inspection.due_date is not None
        else "-",
    )
    pdf.set_font("helvetica", style="I", size=9)
    pdf.set_text_color(82, 97, 111)
    pdf.multi_cell(
        0,
        5,
        f"{intyg.next_inspection.basis} (härledd uppgift)",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_text_color(24, 33, 43)
    pdf.ln(4)
    pdf.set_font("helvetica", size=9)
    pdf.multi_cell(
        0,
        5,
        f"Utfärdat {intyg.issued_date.isoformat()} · Besiktnings-ID {intyg.inspection_id}. "
        "Byggnadens ägare ansvarar för att intyget anslås på väl synlig plats i byggnaden.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    return bytes(pdf.output())
