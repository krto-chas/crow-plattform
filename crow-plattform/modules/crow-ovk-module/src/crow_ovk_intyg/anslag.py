"""Renderar OVK-intyget som anslag för uppsättning på väl synlig plats i byggnaden."""

from __future__ import annotations

from html import escape

from .models import IntygResult, OvkIntyg

_RESULT_LABELS = {
    IntygResult.GODKAND: "GODKÄND",
    IntygResult.EJ_GODKAND: "EJ GODKÄND",
}

_TYPE_LABELS = {
    "forstagang": "Förstagångsbesiktning",
    "aterkommande": "Återkommande besiktning",
}


def intyg_html(intyg: OvkIntyg) -> str:
    result_label = _RESULT_LABELS[intyg.result]
    result_class = "pass" if intyg.result is IntygResult.GODKAND else "fail"
    kontrollant = intyg.funktionskontrollant
    valid_to = (
        kontrollant.certificate_valid_to.isoformat()
        if kontrollant.certificate_valid_to is not None
        else "—"
    )
    system_rows = (
        "".join(
            "<tr>"
            f"<td>{escape(system.system_id)}</td>"
            f"<td>{escape(system.system_type)}</td>"
            f"<td>{escape(system.label)}</td>"
            f"<td>{escape(_RESULT_LABELS[system.result])}</td>"
            "</tr>"
            for system in intyg.systems
        )
        or '<tr><td colspan="4">Inga system registrerade.</td></tr>'
    )
    if intyg.next_inspection.due_date is not None:
        next_line = f"Senast {escape(intyg.next_inspection.due_date.isoformat())}"
    else:
        next_line = "—"
    inspection_type = _TYPE_LABELS.get(
        intyg.inspection_type.value, escape(intyg.inspection_type.value)
    )
    return f"""<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><title>OVK-intyg {escape(intyg.intyg_id)}</title>
<style>
body{{font-family:Georgia,serif;color:#18212b;max-width:760px;margin:40px auto;padding:0 24px}}
h1{{font-size:26px;letter-spacing:2px;border-bottom:3px double #18212b;padding-bottom:8px}}
table{{width:100%;border-collapse:collapse;margin:14px 0}}
td,th{{border:1px solid #8a97a3;padding:7px 9px;text-align:left;font-size:14px}}
th{{background:#eef2f5}}
.result{{font-size:30px;font-weight:700;text-align:center;padding:18px;border:3px solid}}
.result.pass{{color:#1c6b34;border-color:#1c6b34;background:#e5f6ea}}
.result.fail{{color:#8f2020;border-color:#8f2020;background:#fbe9e9}}
.basis{{font-size:12px;color:#52616f;font-style:italic}}
footer{{margin-top:28px;font-size:12px;color:#52616f;border-top:1px solid #cbd4dc;padding-top:10px}}
</style></head><body>
<h1>OVK-INTYG</h1>
<p>Intyg över obligatorisk ventilationskontroll enligt plan- och bygglagstiftningen.</p>
<table>
<tr><th>Fastighetsbeteckning</th><td>{escape(intyg.fastighetsbeteckning)}</td></tr>
<tr><th>Byggnad</th><td>{escape(intyg.object_name)} ({escape(intyg.building_id)})</td></tr>
<tr><th>Adress</th><td>{escape(intyg.address or "—")}</td></tr>
<tr><th>Byggnadens ägare</th><td>{escape(intyg.byggnadsagare.name)}</td></tr>
<tr><th>Besiktningstyp</th><td>{inspection_type}</td></tr>
<tr><th>Besiktningsdatum</th><td>{escape(intyg.inspection_date.isoformat())}</td></tr>
</table>
<h2>Funktionskontrollant</h2>
<table>
<tr><th>Namn</th><td>{escape(kontrollant.name)}</td></tr>
<tr><th>Behörighet</th><td>{escape(kontrollant.behorighet.value)}</td></tr>
<tr><th>Certifieringsorgan</th><td>{escape(kontrollant.certification_body)}</td></tr>
<tr><th>Certifikatnummer</th><td>{escape(kontrollant.certificate_number)}</td></tr>
<tr><th>Certifikat giltigt t.o.m.</th><td>{escape(valid_to)}</td></tr>
</table>
<h2>Omfattade ventilationssystem</h2>
<table><tr><th>System</th><th>Typ</th><th>Benämning</th><th>Resultat</th></tr>{system_rows}</table>
<div class="result {result_class}">{result_label}</div>
<table>
<tr><th>Nästa besiktning</th><td>{next_line}</td></tr>
</table>
<p class="basis">{escape(intyg.next_inspection.basis)} (härledd uppgift)</p>
<footer>
Utfärdat {escape(intyg.issued_date.isoformat())} · Intygs-ID {escape(intyg.intyg_id)} ·
Besiktnings-ID {escape(intyg.inspection_id)}<br>
Byggnadens ägare ansvarar för att detta intyg anslås på väl synlig plats i byggnaden.
</footer>
</body></html>"""
