from __future__ import annotations

from html import escape

from .models import OvkWorkflowRecord


def protocol_html(record: OvkWorkflowRecord) -> str:
    if not record.protocol_ready:
        raise ValueError("OVK workflow is not protocol ready")

    inspection = record.inspection
    ovk_object = inspection.ovk_object
    system_rows = "".join(
        "<tr>"
        f"<td>{escape(system.system_id)}</td>"
        f"<td>{escape(system.system_type)}</td>"
        f"<td>{escape(system.label)}</td>"
        "</tr>"
        for system in inspection.systems
    ) or '<tr><td colspan="3">Inga system registrerade.</td></tr>'

    checkpoint_rows = "".join(
        "<tr>"
        f"<td>{escape(item.label)}</td>"
        f"<td>{escape(item.system_id or '—')}</td>"
        f"<td>{escape(item.status.value)}</td>"
        f"<td>{escape(item.note)}</td>"
        "</tr>"
        for item in inspection.checkpoints
    )

    measurement_rows = "".join(
        "<tr>"
        f"<td>{escape(item.point_id or '—')}</td>"
        f"<td>{escape(item.system_id or '—')}</td>"
        f"<td>{escape(item.metric)}</td>"
        f"<td>{escape(str(item.measured_value))} {escape(item.unit)}</td>"
        f"<td>{escape(str(item.designed_value) if item.designed_value is not None else '—')}</td>"
        f"<td>{escape(str(item.deviation_percent) if item.deviation_percent is not None else '—')}</td>"
        "</tr>"
        for item in inspection.measurements
    ) or '<tr><td colspan="6">Inga mätningar registrerade.</td></tr>'

    finding_rows = "".join(
        "<tr>"
        f"<td>{escape(item.system_id or '—')}</td>"
        f"<td>{escape(item.severity.value)}</td>"
        f"<td>{escape(item.description)}</td>"
        f"<td>{'Ja' if item.action_required else 'Nej'}</td>"
        "</tr>"
        for item in inspection.findings
    ) or '<tr><td colspan="4">Inga findings registrerade.</td></tr>'

    return f"""<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><title>OVK-protokoll</title>
<style>
body{{font-family:Arial,sans-serif;color:#111;margin:32px;font-size:12px}}
h1{{margin-bottom:4px}}h2{{margin-top:24px}}table{{width:100%;border-collapse:collapse}}
th,td{{border:1px solid #bbb;padding:6px;text-align:left;vertical-align:top}}
.meta{{display:grid;grid-template-columns:1fr 1fr;gap:8px 24px}}
@media print{{body{{margin:12mm}}}}
</style></head><body>
<h1>OVK-protokoll</h1>
<p>Genererat från sparad Crow-besiktning. Ingen normbedömning har lagts till av exporten.</p>
<div class="meta">
<div><strong>Objekt:</strong> {escape(ovk_object.name)}</div>
<div><strong>Adress:</strong> {escape(ovk_object.address or '—')}</div>
<div><strong>Projekt:</strong> {escape(ovk_object.project_id)}</div>
<div><strong>Besiktning:</strong> {escape(inspection.inspection_id)}</div>
<div><strong>Byggnad:</strong> {escape(ovk_object.building_id)}</div>
<div><strong>Slutsats:</strong> {escape(inspection.conclusion.value)}</div>
</div>
<h2>Ventilationssystem</h2><table><thead><tr><th>ID</th><th>Typ</th><th>Namn</th></tr></thead><tbody>{system_rows}</tbody></table>
<h2>Kontrollpunkter</h2><table><thead><tr><th>Kontroll</th><th>System</th><th>Status</th><th>Notering</th></tr></thead><tbody>{checkpoint_rows}</tbody></table>
<h2>Mätningar</h2><table><thead><tr><th>Punkt</th><th>System</th><th>Mätetal</th><th>Uppmätt</th><th>Projekterat</th><th>Avvikelse %</th></tr></thead><tbody>{measurement_rows}</tbody></table>
<h2>Findings</h2><table><thead><tr><th>System</th><th>Allvar</th><th>Beskrivning</th><th>Åtgärd krävs</th></tr></thead><tbody>{finding_rows}</tbody></table>
<p><strong>Senast sparad:</strong> {escape(record.updated_at)}</p>
</body></html>"""
