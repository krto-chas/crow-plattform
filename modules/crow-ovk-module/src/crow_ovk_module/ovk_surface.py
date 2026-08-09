# ruff: noqa: E501
from __future__ import annotations

from hashlib import sha256
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from crow_observation_engine.models import (
    Observation,
    ObservationCollection,
    ObservationEvidence,
    ObservationSource,
    ObservationType,
    SourceLocator,
)
from crow_ovk_import import import_observations


def ovk_router() -> APIRouter:
    router = APIRouter()

    @router.get("/ovk", response_class=HTMLResponse)
    def ovk_page() -> str:
        return _OVK_HTML

    @router.post("/api/ovk/projects/{project_id}/import-preview", response_model=None)
    async def import_preview(project_id: str, request: Request) -> dict[str, Any]:
        payload: Any = await request.json()
        rows = payload.get("observations") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_OVK_IMPORT", "message": "observations must be a non-empty list"},
            )

        observations: list[Observation] = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IMPORT_ROW"})
            text = str(row.get("text", "")).strip()
            if not text:
                raise HTTPException(status_code=422, detail={"code": "EMPTY_OVK_IMPORT_ROW"})
            document_id = _text(row.get("document_id")) or "workbench-input"
            page_number = _positive_int(row.get("page_number"), default=1)
            region_id = _text(row.get("region_id")) or f"row-{index}"
            digest = sha256(text.encode("utf-8")).hexdigest()
            observations.append(
                Observation(
                    id=f"ovk-preview-{index}",
                    observation_type=ObservationType.TEXT,
                    value=text,
                    normalized_value=text,
                    content_sha256=digest,
                    evidence=ObservationEvidence(
                        source=ObservationSource.EMBEDDED_PDF_TEXT,
                        source_text=text,
                        confidence=1.0,
                        locator=SourceLocator(
                            document_id=document_id,
                            page_id=f"{document_id}:page:{page_number}",
                            page_number=page_number,
                            region_id=region_id,
                            character_start=0,
                            character_end=len(text),
                        ),
                        page_sha256=_text(row.get("page_sha256")) or f"preview-page-{page_number}",
                    ),
                )
            )

        result = import_observations(
            ObservationCollection(project_id=project_id, observations=tuple(observations))
        )
        return {
            "project_id": result.project_id,
            "systems": [
                {
                    "system_id": item.system_id,
                    "system_type": item.system_type,
                    "label": item.label,
                    "source_ref": item.source_ref,
                }
                for item in result.systems
            ],
            "measurements": [
                {
                    "measurement_id": item.measurement_id,
                    "metric": item.metric,
                    "measured_value": str(item.measured_value),
                    "designed_value": (
                        None if item.designed_value is None else str(item.designed_value)
                    ),
                    "deviation_percent": (
                        None if item.deviation_percent is None else str(item.deviation_percent)
                    ),
                    "unit": item.unit,
                    "system_id": item.system_id,
                    "point_id": item.point_id,
                    "origin": item.origin.value,
                    "evidence_ref": item.evidence_ref,
                }
                for item in result.measurements
            ],
            "findings": [
                {
                    "finding_id": item.finding_id,
                    "description": item.description,
                    "severity": item.severity.value,
                    "system_id": item.system_id,
                    "action_required": item.action_required,
                    "origin": item.origin.value,
                    "evidence_ref": item.evidence_ref,
                }
                for item in result.findings
            ],
            "review": [
                {
                    "observation_id": item.observation_id,
                    "source_text": item.source_text,
                    "evidence_ref": item.evidence_ref,
                    "reason": item.reason,
                }
                for item in result.unmapped
            ],
        }

    return router


def _text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _positive_int(value: object, *, default: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


_OVK_HTML = r'''<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Crow OVK</title>
<style>
:root{font-family:Inter,system-ui,sans-serif;color:#18212b;background:#f4f6f8}body{margin:0}.shell{display:grid;grid-template-columns:230px 1fr;min-height:100vh}aside{background:#17202a;color:#fff;padding:24px}aside h1{font-size:20px;margin:0 0 28px}nav a{display:block;color:#dce5ed;text-decoration:none;padding:10px 0}nav a.active{font-weight:700;color:#fff}main{padding:32px;max-width:1300px}.eyebrow{font-size:12px;letter-spacing:.12em;color:#687684}.grid{display:grid;grid-template-columns:420px 1fr;gap:18px}.panel{background:#fff;border:1px solid #dfe5ea;border-radius:10px;padding:20px}label{display:block;font-size:13px;font-weight:600;margin:12px 0 5px}select,input,textarea{width:100%;box-sizing:border-box;padding:9px;border:1px solid #cbd4dc;border-radius:6px}textarea{min-height:210px;resize:vertical}.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}.primary{margin-top:16px;padding:10px 14px;border:0;border-radius:6px;background:#17202a;color:#fff;cursor:pointer}.status{padding:12px;border-radius:6px;background:#eef2f5;margin-top:12px}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}.metric{background:#f5f7f9;padding:12px;border-radius:6px}.metric strong{display:block;font-size:20px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;border-bottom:1px solid #e6eaee;padding:8px;vertical-align:top}.section{margin-top:22px}.badge{display:inline-block;padding:3px 7px;border-radius:12px;background:#e8edf1;font-size:11px;font-weight:700}.review{background:#fff4cf}.empty{color:#687684;font-size:13px}.help{font-size:13px;color:#52616f;line-height:1.45}@media(max-width:900px){.shell{grid-template-columns:1fr}aside{display:none}.grid{grid-template-columns:1fr}.summary,.two{grid-template-columns:1fr 1fr}}
</style></head><body><div class="shell"><aside><h1>Crow</h1><nav><a href="/">Projekt</a><a href="/vent">Ventilation</a><a href="/provtryckning">Provtryckning</a><a class="active" href="/ovk">OVK</a></nav></aside><main><p class="eyebrow">OVK</p><h2>Import & granskningsyta</h2><p>Förhandsgranska dokumentevidens innan den används i en OVK-besiktning. Crow gissar inte betydelsen av oetiketterade värden.</p><div class="grid"><section class="panel"><label>Projekt</label><select id="project"><option value="adhoc">Ad hoc</option></select><div class="two"><div><label>Dokument-ID</label><input id="document" value="ovk-protokoll"></div><div><label>Sida</label><input id="page" type="number" min="1" value="1"></div></div><label>Evidensrader</label><textarea id="rows" placeholder="En observation per rad">System FTX01, B1 uppmätt 34,5 l/s, projekterat 40 l/s
Anmärkning: Filter i FTX02 är smutsigt
B1 FTX03 34 l/s 40 l/s</textarea><p class="help">Varje rad blir en separat evidensobservation. Rader med explicit uppmätt/projekterat värde kan mappas. Oetiketterade luftflöden hamnar i review även om system-ID:t kan identifieras.</p><button class="primary" id="preview">Analysera import</button><div id="message" class="status">Klar för importförhandsgranskning.</div></section><section class="panel"><div id="summary" class="summary"></div><div class="section"><h3>System</h3><div id="systems" class="empty">Ingen import ännu.</div></div><div class="section"><h3>Mätningar</h3><div id="measurements" class="empty">Ingen import ännu.</div></div><div class="section"><h3>Tidigare findings</h3><div id="findings" class="empty">Ingen import ännu.</div></div><div class="section"><h3>Review-kö</h3><div id="review" class="empty">Ingen import ännu.</div></div></section></div></main></div>
<script>
const $=id=>document.getElementById(id);
function esc(value){return String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))}
async function init(){const modules=await fetch('/api/me/modules');if(!modules.ok){$('message').textContent='OVK är inte tillgänglig: '+modules.status;return}const data=await modules.json();if(!(data.modules||[]).some(m=>m.id==='ovk')){$('message').textContent='OVK ingår inte i licensen.';$('preview').disabled=true;return}const projects=await fetch('/api/projects');if(projects.ok){for(const p of await projects.json()){const o=document.createElement('option');o.value=p.project_id;o.textContent=p.project_name||p.name||p.project_id;$('project').appendChild(o)}}}
$('preview').onclick=async()=>{const lines=$('rows').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);if(!lines.length){$('message').textContent='Lägg in minst en evidensrad.';return}const observations=lines.map((text,i)=>({text,document_id:$('document').value,page_number:Number($('page').value)||1,region_id:'workbench-row-'+(i+1)}));$('message').textContent='Analyserar…';const r=await fetch('/api/ovk/projects/'+encodeURIComponent($('project').value)+'/import-preview',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({observations})});const data=await r.json();if(!r.ok){$('message').textContent='Fel: '+JSON.stringify(data);return}render(data);$('message').textContent='Importförhandsgranskning klar.'};
function table(headers,rows){if(!rows.length)return '<div class="empty">Inga poster.</div>';return '<table><thead><tr>'+headers.map(h=>'<th>'+h+'</th>').join('')+'</tr></thead><tbody>'+rows.join('')+'</tbody></table>'}
function render(d){$('summary').innerHTML=[['System',d.systems.length],['Mätningar',d.measurements.length],['Findings',d.findings.length],['Review',d.review.length]].map(x=>'<div class="metric"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join('');$('systems').innerHTML=table(['System','Typ','Källa'],d.systems.map(x=>'<tr><td><strong>'+esc(x.system_id)+'</strong></td><td>'+esc(x.system_type)+'</td><td>'+esc(x.source_ref)+'</td></tr>'));$('measurements').innerHTML=table(['Punkt','System','Uppmätt','Projekterat','Avvikelse','Källa'],d.measurements.map(x=>'<tr><td>'+esc(x.point_id||'—')+'</td><td>'+esc(x.system_id||'—')+'</td><td>'+esc(x.measured_value)+' '+esc(x.unit)+'</td><td>'+esc(x.designed_value??'—')+'</td><td>'+esc(x.deviation_percent===null?'—':x.deviation_percent+' %')+'</td><td>'+esc(x.evidence_ref)+'</td></tr>'));$('findings').innerHTML=table(['System','Beskrivning','Origin','Källa'],d.findings.map(x=>'<tr><td>'+esc(x.system_id||'—')+'</td><td>'+esc(x.description)+'</td><td><span class="badge">'+esc(x.origin.toUpperCase())+'</span></td><td>'+esc(x.evidence_ref)+'</td></tr>'));$('review').innerHTML=table(['Orsak','Källtext','Källa'],d.review.map(x=>'<tr class="review"><td>'+esc(x.reason)+'</td><td>'+esc(x.source_text)+'</td><td>'+esc(x.evidence_ref)+'</td></tr>'))}
init();
</script></body></html>'''
