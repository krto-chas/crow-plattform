# ruff: noqa: E501
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from crow_ovk_workflow import (
    OvkReinspectionCase,
    OvkReinspectionRepository,
    OvkWorkflowRepository,
    case_to_payload,
    claim_remedy,
    close_case,
    open_case,
    verify_item,
)


def ovk_reinspection_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    workflow_repository = OvkWorkflowRepository(data_root)
    case_repository = OvkReinspectionRepository(data_root)

    @router.get("/ovk/ombesiktning", response_class=HTMLResponse)
    def reinspection_page() -> str:
        return _REINSPECTION_HTML

    @router.get("/api/ovk/projects/{project_id}/ombesiktning", response_model=None)
    def list_cases(project_id: str) -> dict[str, Any]:
        try:
            cases = case_repository.list(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_PROJECT"}) from exc
        return {
            "project_id": project_id,
            "cases": [
                {
                    "case_id": case.case_id,
                    "source_inspection_id": case.source_inspection_id,
                    "status": case.status.value,
                    "deadline": case.deadline.isoformat() if case.deadline else None,
                    "result_inspection_id": case.result_inspection_id,
                    "open_items": sum(item.state.value != "verified" for item in case.items),
                }
                for case in cases
            ],
        }

    @router.get("/api/ovk/projects/{project_id}/ombesiktning/{case_id}", response_model=None)
    def get_case(project_id: str, case_id: str) -> dict[str, Any]:
        return case_to_payload(_load_case(case_repository, project_id, case_id))

    @router.post(
        "/api/ovk/projects/{project_id}/inspections/{inspection_id}/ombesiktning",
        response_model=None,
    )
    async def open_reinspection_case(
        project_id: str, inspection_id: str, request: Request
    ) -> dict[str, Any]:
        payload = await _json_object(request)
        record = _load_record(workflow_repository, project_id, inspection_id)
        try:
            case = open_case(
                record,
                case_id=_required(payload, "case_id"),
                deadline=_optional_date(payload.get("deadline")),
            )
            case_repository.save(case)
        except ValueError as exc:
            message = str(exc)
            if "protocol ready" in message or "deficiencies" in message:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "OVK_CASE_NOT_OPENABLE",
                        "conclusion": record.inspection.conclusion.value,
                        "message": message,
                    },
                ) from exc
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_OVK_CASE", "message": message}
            ) from exc
        return case_to_payload(case)

    @router.post(
        "/api/ovk/projects/{project_id}/ombesiktning/{case_id}/remedy",
        response_model=None,
    )
    async def claim(project_id: str, case_id: str, request: Request) -> dict[str, Any]:
        payload = await _json_object(request)
        case = _load_case(case_repository, project_id, case_id)
        try:
            case = claim_remedy(
                case,
                _required(payload, "finding_id"),
                note=_required(payload, "note"),
                evidence_ref=_optional(payload.get("evidence_ref")),
            )
            case_repository.save(case)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_OVK_REMEDY", "message": str(exc)}
            ) from exc
        return case_to_payload(case)

    @router.post(
        "/api/ovk/projects/{project_id}/ombesiktning/{case_id}/verify",
        response_model=None,
    )
    async def verify(project_id: str, case_id: str, request: Request) -> dict[str, Any]:
        payload = await _json_object(request)
        case = _load_case(case_repository, project_id, case_id)
        try:
            case = verify_item(
                case,
                _required(payload, "finding_id"),
                verified=bool(payload.get("verified", False)),
                reinspection_id=_required(payload, "reinspection_id"),
                note=str(payload.get("note", "")),
            )
            case_repository.save(case)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_OVK_VERIFICATION", "message": str(exc)}
            ) from exc
        return case_to_payload(case)

    @router.post(
        "/api/ovk/projects/{project_id}/ombesiktning/{case_id}/close",
        response_model=None,
    )
    async def close(project_id: str, case_id: str, request: Request) -> dict[str, Any]:
        payload = await _json_object(request)
        case = _load_case(case_repository, project_id, case_id)
        reinspection_id = _required(payload, "reinspection_id")
        record = _load_record(workflow_repository, project_id, reinspection_id)
        try:
            case = close_case(case, reinspection_record=record)
            case_repository.save(case)
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "OVK_CASE_NOT_CLOSABLE", "message": str(exc)},
            ) from exc
        return case_to_payload(case)

    return router


def _load_case(
    repository: OvkReinspectionRepository, project_id: str, case_id: str
) -> OvkReinspectionCase:
    try:
        return repository.load(project_id, case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "OVK_CASE_NOT_FOUND"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"}) from exc


def _load_record(repository: OvkWorkflowRepository, project_id: str, inspection_id: str) -> Any:
    try:
        return repository.load(project_id, inspection_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "OVK_INSPECTION_NOT_FOUND"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"}) from exc


async def _json_object(request: Request) -> dict[str, Any]:
    payload: Any = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_CASE"})
    return payload


def _required(item: dict[str, Any], key: str) -> str:
    value = _optional(item.get(key))
    if value is None:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_OVK_CASE", "message": f"{key} is required"}
        )
    return value


def _optional(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _optional_date(value: object) -> date | None:
    text = _optional(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_OVK_CASE", "message": f"invalid date {text!r}"},
        ) from exc


_REINSPECTION_HTML = r"""<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Crow OVK Ombesiktning</title>
<style>:root{font-family:Inter,system-ui,sans-serif;color:#18212b;background:#f4f6f8}*{box-sizing:border-box}body{margin:0}.shell{display:grid;grid-template-columns:230px 1fr;min-height:100vh}aside{background:#17202a;color:#fff;padding:24px}nav a{display:block;color:#dce5ed;text-decoration:none;padding:10px 0}nav a.active{font-weight:700;color:#fff}main{padding:32px;max-width:1200px}.grid{display:grid;grid-template-columns:400px 1fr;gap:18px}.panel{background:#fff;border:1px solid #dfe5ea;border-radius:10px;padding:20px}label{display:block;font-size:13px;font-weight:600;margin:10px 0 4px}input,select{width:100%;padding:8px;border:1px solid #cbd4dc;border-radius:6px}.primary,.secondary{margin-top:10px;padding:10px 14px;border-radius:6px;cursor:pointer}.primary{border:0;background:#17202a;color:#fff}.secondary{border:1px solid #aeb9c3;background:#fff}.status{margin-top:12px;padding:10px;background:#eef2f5;border-radius:6px}.warning{background:#fff4cf}.pass{background:#e5f6ea}.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}.item{border:1px solid #dfe5ea;border-radius:8px;padding:12px;margin-top:10px}.badge{display:inline-block;padding:3px 8px;border-radius:12px;font-size:11px;font-weight:700;background:#e8edf1}.badge.verified{background:#e5f6ea}.badge.failed{background:#fbe9e9}.badge.remedy_claimed{background:#fff4cf}.muted{font-size:12px;color:#607080}pre{white-space:pre-wrap;background:#f7f8fa;padding:12px;border-radius:6px;max-height:280px;overflow:auto}@media(max-width:900px){.shell{grid-template-columns:1fr}aside{display:none}.grid{grid-template-columns:1fr}.two{grid-template-columns:1fr}}</style></head>
<body><div class="shell"><aside><h2>Crow</h2><nav><a href="/">Projekt</a><a href="/vent">Ventilation</a><a href="/provtryckning">Provtryckning</a><a href="/ovk">OVK import</a><a href="/ovk/besiktning">OVK besiktning</a><a href="/ovk/falt">OVK fält</a><a href="/ovk/intyg">OVK intyg</a><a class="active" href="/ovk/ombesiktning">OVK ombesiktning</a></nav></aside><main><p>OVK · OMBESIKTNING</p><h1>Ombesiktningsärenden</h1><p>Kedjan underkänd → åtgärd uppgiven (STATED) → verifierad vid ombesiktning (OBSERVED) → ärende stängt mot godkänt ombesiktningsrecord.</p><div class="grid"><section class="panel"><label>Projekt</label><select id="project"><option value="adhoc">Ad hoc</option></select><label>Underkänd besiktning (ID)</label><input id="inspection" value="ovk-001"><label>Ärende-ID</label><input id="case" value="omb-001"><label>Åtgärdsfrist (valfri)</label><input id="deadline" type="date"><button class="primary" id="open">Öppna ärende</button><button class="secondary" id="load">Ladda ärende</button><button class="secondary" id="list">Lista ärenden</button><hr><label>Ombesiktningens besiktnings-ID</label><input id="reinspection" value="ovk-001-omb"><button class="secondary" id="close">Stäng ärende mot godkänd ombesiktning</button><div id="message" class="status">Klar.</div></section><section class="panel"><h3>Punkter</h3><div id="items" class="muted">Inget ärende laddat.</div><h3>Ärende</h3><pre id="result">—</pre><div id="cases"></div></section></div></main></div>
<script>
const $=id=>document.getElementById(id);let current=null;function ensureProject(id){if(!id)return;if(![...$('project').options].some(o=>o.value===id)){const option=document.createElement('option');option.value=id;option.textContent=id;$('project').appendChild(option)}}
async function init(){const modules=await fetch('/api/me/modules');if(!modules.ok)return;const data=await modules.json();if(!(data.modules||[]).some(m=>m.id==='ovk')){$('message').textContent='OVK ingår inte i licensen.';$('open').disabled=true;return}const projects=await fetch('/api/projects');if(projects.ok){for(const p of await projects.json()){ensureProject(p.project_id);const o=[...$('project').options].find(x=>x.value===p.project_id);if(o)o.textContent=p.project_name||p.name||p.project_id}}}
function base(){return '/api/ovk/projects/'+encodeURIComponent($('project').value)+'/ombesiktning'}
function render(d){current=d;$('result').textContent=JSON.stringify(d,null,2);$('items').innerHTML=d.items.map(item=>{const actions=d.closed_at?'':'<div class="two"><button class="secondary" onclick="claim(\''+item.finding_id+'\')">Uppge åtgärdad</button><button class="secondary" onclick="verify(\''+item.finding_id+'\',true)">Verifiera OK</button></div>'+(d.closed_at?'':'<button class="secondary" onclick="verify(\''+item.finding_id+'\',false)">Kvarstår (underkänd)</button>');return '<div class="item"><strong>'+item.finding_id+'</strong> <span class="badge '+item.state+'">'+item.state+'</span><div>'+item.description+'</div><div class="muted">'+(item.system_id||'utan system')+' · '+item.severity+(item.remedy_note?' · Åtgärd: '+item.remedy_note:'')+(item.verified_in?' · Verifierad i: '+item.verified_in:'')+'</div>'+actions+'</div>'}).join('');$('message').className='status '+(d.status==='ready'?'pass':d.status==='closed'?'pass':'warning');$('message').textContent='Status: '+d.status+(d.status==='ready'?' — alla punkter verifierade, kan stängas.':d.status==='closed'?' — stängd mot '+d.result_inspection_id+'.':' — punkter kvarstår.')}
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok){$('message').className='status warning';$('message').textContent='Fel: '+JSON.stringify(d);return null}return d}
window.claim=async id=>{const note=prompt('Åtgärdsnotering (obligatorisk):');if(!note)return;const d=await post(base()+'/'+encodeURIComponent($('case').value)+'/remedy',{finding_id:id,note});if(d)render(d)};
window.verify=async(id,ok)=>{const d=await post(base()+'/'+encodeURIComponent($('case').value)+'/verify',{finding_id:id,verified:ok,reinspection_id:$('reinspection').value});if(d)render(d)};
$('open').onclick=async()=>{const d=await post('/api/ovk/projects/'+encodeURIComponent($('project').value)+'/inspections/'+encodeURIComponent($('inspection').value)+'/ombesiktning',{case_id:$('case').value,deadline:$('deadline').value||null});if(d)render(d)};
$('load').onclick=async()=>{const r=await fetch(base()+'/'+encodeURIComponent($('case').value));const d=await r.json();if(!r.ok){$('message').textContent='Fel: '+JSON.stringify(d);return}render(d)};
$('list').onclick=async()=>{const r=await fetch(base());const d=await r.json();if(!r.ok)return;$('cases').innerHTML=d.cases.map(c=>'<div class="item"><strong>'+c.case_id+'</strong> <span class="badge">'+c.status+'</span><div class="muted">Källa: '+c.source_inspection_id+' · Öppna punkter: '+c.open_items+(c.deadline?' · Frist: '+c.deadline:'')+(c.result_inspection_id?' · Stängd mot: '+c.result_inspection_id:'')+'</div></div>').join('')};
$('close').onclick=async()=>{const d=await post(base()+'/'+encodeURIComponent($('case').value)+'/close',{reinspection_id:$('reinspection').value});if(d)render(d)};
init();
</script></body></html>"""
