# ruff: noqa: E501
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from crow_ovk_workflow import OvkWorkflowRepository, protocol_html, record_from_payload, record_to_payload


def ovk_workflow_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    repository = OvkWorkflowRepository(data_root)

    @router.get("/ovk/besiktning", response_class=HTMLResponse)
    def workflow_page() -> str:
        return _WORKFLOW_HTML

    @router.get("/api/ovk/projects/{project_id}/inspections", response_model=None)
    def list_inspections(project_id: str) -> dict[str, Any]:
        try:
            records = repository.list(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_PROJECT"}) from exc
        return {
            "project_id": project_id,
            "inspections": [
                {
                    "inspection_id": record.inspection.inspection_id,
                    "object_name": record.inspection.ovk_object.name,
                    "conclusion": record.inspection.conclusion.value,
                    "protocol_ready": record.protocol_ready,
                    "unresolved_review_count": record.unresolved_review_count,
                    "updated_at": record.updated_at,
                }
                for record in records
            ],
        }

    @router.get(
        "/api/ovk/projects/{project_id}/inspections/{inspection_id}",
        response_model=None,
    )
    def get_inspection(project_id: str, inspection_id: str) -> dict[str, Any]:
        return record_to_payload(_load(repository, project_id, inspection_id))

    @router.put(
        "/api/ovk/projects/{project_id}/inspections/{inspection_id}",
        response_model=None,
    )
    async def save_inspection(
        project_id: str,
        inspection_id: str,
        request: Request,
    ) -> dict[str, Any]:
        payload: Any = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_WORKFLOW"})
        candidate = dict(payload)
        inspection = candidate.get("inspection")
        if not isinstance(inspection, dict):
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_INSPECTION"})
        inspection = dict(inspection)
        inspection["inspection_id"] = inspection_id
        object_payload = inspection.get("object")
        if not isinstance(object_payload, dict):
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_OBJECT"})
        object_payload = dict(object_payload)
        object_payload["project_id"] = project_id
        inspection["object"] = object_payload
        candidate["inspection"] = inspection
        try:
            record = record_from_payload(candidate)
            repository.save(record)
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_OVK_WORKFLOW", "message": str(exc)},
            ) from exc
        return record_to_payload(record)

    @router.get(
        "/api/ovk/projects/{project_id}/inspections/{inspection_id}/protocol",
        response_class=HTMLResponse,
    )
    def export_protocol(project_id: str, inspection_id: str) -> str:
        record = _load(repository, project_id, inspection_id)
        try:
            return protocol_html(record)
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OVK_PROTOCOL_NOT_READY",
                    "conclusion": record.inspection.conclusion.value,
                    "unresolved_review_count": record.unresolved_review_count,
                },
            ) from exc

    return router


def _load(
    repository: OvkWorkflowRepository,
    project_id: str,
    inspection_id: str,
):
    try:
        return repository.load(project_id, inspection_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "OVK_INSPECTION_NOT_FOUND"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"}) from exc


_WORKFLOW_HTML = r'''<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Crow OVK Besiktning</title>
<style>:root{font-family:Inter,system-ui,sans-serif;color:#18212b;background:#f4f6f8}body{margin:0}.shell{display:grid;grid-template-columns:230px 1fr;min-height:100vh}aside{background:#17202a;color:#fff;padding:24px}nav a{display:block;color:#dce5ed;text-decoration:none;padding:10px 0}nav a.active{font-weight:700;color:#fff}main{padding:32px;max-width:1250px}.grid{display:grid;grid-template-columns:400px 1fr;gap:18px}.panel{background:#fff;border:1px solid #dfe5ea;border-radius:10px;padding:20px}label{display:block;font-size:13px;font-weight:600;margin:10px 0 4px}input,select,textarea{width:100%;box-sizing:border-box;padding:8px;border:1px solid #cbd4dc;border-radius:6px}textarea{min-height:120px}.primary{margin-top:14px;padding:10px 14px;border:0;border-radius:6px;background:#17202a;color:#fff;cursor:pointer}.secondary{margin-top:8px;padding:9px 12px;border:1px solid #aeb9c3;border-radius:6px;background:#fff;cursor:pointer}.status{margin-top:12px;padding:10px;background:#eef2f5;border-radius:6px}.warning{background:#fff4cf}.pass{background:#e5f6ea}.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}.help{font-size:12px;color:#607080;line-height:1.45}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.metric{background:#f5f7f9;padding:12px;border-radius:6px}.metric strong{display:block;font-size:18px}pre{white-space:pre-wrap;background:#f7f8fa;padding:12px;border-radius:6px;max-height:440px;overflow:auto}@media(max-width:900px){.shell{grid-template-columns:1fr}aside{display:none}.grid{grid-template-columns:1fr}.summary{grid-template-columns:1fr 1fr}}</style></head>
<body><div class="shell"><aside><h2>Crow</h2><nav><a href="/">Projekt</a><a href="/vent">Ventilation</a><a href="/provtryckning">Provtryckning</a><a href="/ovk">OVK import</a><a class="active" href="/ovk/besiktning">OVK besiktning</a></nav></aside><main><p>OVK · BESIKTNINGSWORKFLOW</p><h1>Sparad OVK-besiktning</h1><p>Skapa eller uppdatera ett evidensbärande besiktningsutkast. Crow lägger inte till normativa slutsatser utöver explicit status på kontrollpunkterna.</p><div class="grid"><section class="panel"><label>Projekt</label><select id="project"><option value="adhoc">Ad hoc</option></select><label>Besiktnings-ID</label><input id="inspection" value="ovk-001"><div class="two"><div><label>Byggnads-ID</label><input id="building" value="building-1"></div><div><label>Objekt-ID</label><input id="object" value="object-1"></div></div><label>Objektnamn</label><input id="name" value="OVK-objekt"><label>Adress</label><input id="address"><label>System, ett per rad: ID | typ | namn</label><textarea id="systems" placeholder="FTX01 | FTX | Huvudsystem"></textarea><label>Kontrollpunkter, ett per rad: ID | status | system | beskrivning | notering</label><textarea id="checkpoints" placeholder="cp1 | pass | FTX01 | Drift och funktion | OK"></textarea><label>Reviewbeslut, ett per rad: observation-id | accepted/rejected/pending | reviewer | note</label><textarea id="review"></textarea><p class="help">Mätningar/findings från import kan läggas in via API. Den här första vyn fokuserar på workflow, kontrollpunkter, review och sparning.</p><button class="primary" id="save">Spara besiktning</button><button class="secondary" id="load">Ladda sparad</button><button class="secondary" id="protocol">Öppna protokoll</button><div id="message" class="status">Klar.</div></section><section class="panel"><div id="summary" class="summary"></div><h3>Sparat record</h3><pre id="result">Ingen besiktning laddad.</pre></section></div></main></div>
<script>const $=id=>document.getElementById(id);function split(line){return line.split('|').map(x=>x.trim())}async function init(){const modules=await fetch('/api/me/modules');if(!modules.ok)return;const data=await modules.json();if(!(data.modules||[]).some(m=>m.id==='ovk')){$('message').textContent='OVK ingår inte i licensen.';$('save').disabled=true;return}const projects=await fetch('/api/projects');if(projects.ok){for(const p of await projects.json()){const o=document.createElement('option');o.value=p.project_id;o.textContent=p.project_name||p.name||p.project_id;$('project').appendChild(o)}}}function build(){const systems=$('systems').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean).map(line=>{const [id,type,label]=split(line);return{system_id:id,system_type:type||'unknown',label:label||id,source_ref:null}});const checkpoints=$('checkpoints').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean).map(line=>{const [id,status,system,label,note]=split(line);return{checkpoint_id:id,status:status||'not_checked',system_id:system||null,label:label||id,note:note||'',origin:'observed',evidence_ref:null}});const review=$('review').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean).map(line=>{const [id,status,reviewer,note]=split(line);return{observation_id:id,source_text:'Workbench review '+id,evidence_ref:'workbench:'+id,reason:'manual_review',status:status||'pending',reviewer:reviewer||null,note:note||''}});return{inspection:{inspection_id:$('inspection').value,object:{object_id:$('object').value,project_id:$('project').value,building_id:$('building').value,name:$('name').value,address:$('address').value||null},systems,checkpoints,measurements:[],findings:[],actions:[]},review}}function render(d){$('result').textContent=JSON.stringify(d,null,2);$('summary').innerHTML=[['Slutsats',d.inspection.conclusion],['Kontroller',d.inspection.checkpoints.length],['Review kvar',d.unresolved_review_count],['Protokoll',d.protocol_ready?'KLART':'BLOCKERAT']].map(x=>'<div class="metric"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join('');$('message').className='status '+(d.protocol_ready?'pass':'warning');$('message').textContent=d.protocol_ready?'Sparad och protokollklar.':'Sparad som utkast; protokoll är blockerat tills workflow är komplett.'}$('save').onclick=async()=>{const p=$('project').value,i=$('inspection').value;const r=await fetch('/api/ovk/projects/'+encodeURIComponent(p)+'/inspections/'+encodeURIComponent(i),{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(build())});const d=await r.json();if(!r.ok){$('message').textContent='Fel: '+JSON.stringify(d);return}render(d)};$('load').onclick=async()=>{const p=$('project').value,i=$('inspection').value;const r=await fetch('/api/ovk/projects/'+encodeURIComponent(p)+'/inspections/'+encodeURIComponent(i));const d=await r.json();if(!r.ok){$('message').textContent='Fel: '+JSON.stringify(d);return}render(d)};$('protocol').onclick=()=>{const p=$('project').value,i=$('inspection').value;window.open('/api/ovk/projects/'+encodeURIComponent(p)+'/inspections/'+encodeURIComponent(i)+'/protocol','_blank')};init();</script></body></html>'''
