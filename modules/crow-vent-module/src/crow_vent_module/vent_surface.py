# ruff: noqa: E501
from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse


def vent_router() -> APIRouter:
    router = APIRouter()

    @router.get("/vent", response_class=HTMLResponse)
    def vent_page() -> str:
        return _VENT_HTML

    @router.post("/api/vent/projects/{project_id}/takeoff", response_model=None)
    async def vent_takeoff(project_id: str, request: Request) -> JSONResponse:
        """Stable, entitlement-protected product alias for the existing takeoff pipeline."""
        payload: Any = await request.json()
        transport = httpx.ASGITransport(app=request.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://crow.internal") as client:
            response = await client.post(f"/api/projects/{project_id}/takeoff", json=payload)
        return JSONResponse(status_code=response.status_code, content=response.json())

    return router


_VENT_HTML = r'''<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Crow Vent</title>
<style>
:root{font-family:Inter,system-ui,sans-serif;color:#18212b;background:#f4f6f8}body{margin:0}.shell{display:grid;grid-template-columns:230px 1fr;min-height:100vh}aside{background:#17202a;color:#fff;padding:24px}aside h1{font-size:20px;margin:0 0 28px}nav a{display:block;color:#dce5ed;text-decoration:none;padding:10px 0}nav a.active{font-weight:700;color:#fff}main{padding:32px;max-width:1200px}.eyebrow{font-size:12px;letter-spacing:.12em;color:#687684}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{background:#fff;border:1px solid #dfe5ea;border-radius:10px;padding:20px}label{display:block;font-size:13px;font-weight:600;margin:12px 0 5px}select,textarea{width:100%;box-sizing:border-box;padding:9px;border:1px solid #cbd4dc;border-radius:6px}textarea{min-height:110px;font-family:ui-monospace,monospace}button{padding:10px 14px;border:0;border-radius:6px;cursor:pointer}button.primary{background:#17202a;color:#fff}.actions{display:flex;gap:8px;margin-top:14px}.status{padding:10px;border-radius:6px;background:#eef2f5;margin-top:12px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.metric{background:#f5f7f9;padding:12px;border-radius:6px}.metric strong{display:block;font-size:18px}.rows{overflow:auto;max-height:360px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:8px;border-bottom:1px solid #e6eaee}@media(max-width:800px){.shell{grid-template-columns:1fr}aside{display:none}.grid,.metrics{grid-template-columns:1fr}}
</style></head><body><div class="shell"><aside><h1>Crow</h1><nav><a href="/">Projekt</a><a class="active" href="/vent">Ventilation</a><a href="#">Provtryckning</a><a href="#">OVK</a></nav></aside><main><p class="eyebrow">VENTILATION</p><h2>Mängdning & kalkyl</h2><p>Produktvy över den befintliga evidensdrivna takeoff-kedjan.</p><div class="grid"><section class="panel"><label>Projekt</label><select id="project"><option value="adhoc">Ad hoc</option></select><label>Mängdförteckning</label><textarea id="table" placeholder="T-125;132;m\nTD1;24;st"></textarea><label>Beskrivningstext</label><textarea id="text" placeholder="24 st TD1"></textarea><label>Prisbok (JSON)</label><textarea id="prices" placeholder='{"labour_rate_per_hour":520,"entries":[]}'></textarea><div class="actions"><button class="primary" id="run">Kör kalkyl</button><button id="csv" disabled>Exportera CSV</button></div><div id="status" class="status">Klar för indata.</div></section><section class="panel"><div id="metrics" class="metrics"></div><div class="rows"><table><thead><tr><th>Post</th><th>Mängd</th><th>Enhet</th><th>Status</th></tr></thead><tbody id="resultRows"></tbody></table></div></section></div></main></div>
<script>
let last=null;const $=id=>document.getElementById(id);
async function init(){const modules=await fetch('/api/me/modules');if(!modules.ok){$('status').textContent='Vent är inte tillgänglig: '+modules.status;return}const data=await modules.json();if(!(data.modules||[]).some(m=>m.id==='vent')){$('status').textContent='Vent ingår inte i licensen.';$('run').disabled=true;return}const projects=await fetch('/api/projects');if(projects.ok){for(const p of await projects.json()){const o=document.createElement('option');o.value=p.project_id;o.textContent=p.project_name||p.project_id;$('project').appendChild(o)}}}
function tableRows(){return $('table').value.split(/\n/).map(x=>x.trim()).filter(Boolean).map(x=>x.split(';').map(v=>v.trim()))}function textSegments(){return $('text').value.trim()?[$('text').value.trim()]:[]}
$('run').onclick=async()=>{let book=null;try{book=$('prices').value.trim()?JSON.parse($('prices').value):null}catch(e){$('status').textContent='Ogiltig prisbok-JSON.';return}const body={table_rows:tableRows(),text_segments:textSegments()};if(book)body.price_book=book;$('status').textContent='Kör kalkyl…';const r=await fetch('/api/vent/projects/'+encodeURIComponent($('project').value)+'/takeoff',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok){$('status').textContent='Kalkylfel: '+JSON.stringify(data);return}last=data;render(data);$('csv').disabled=false;$('status').textContent='Kalkyl klar.'};
function render(d){const p=d.priced||{},c=d.consolidated||{};$('metrics').innerHTML=[['Rader',c.line_count||0],['Prissatta',p.priced_line_count||0],['Arbetstid',p.labour_hours_total??'—'],['Totalt',p.grand_total!=null?p.grand_total+' '+(p.currency||'SEK'):'—']].map(x=>'<div class="metric"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join('');const lines=c.lines||[];$('resultRows').innerHTML=lines.map(x=>'<tr><td>'+(x.designation||x.code||x.key||'—')+'</td><td>'+(x.quantity??'—')+'</td><td>'+(x.unit||'—')+'</td><td>'+(x.status||'—')+'</td></tr>').join('')}
$('csv').onclick=()=>{if(!last)return;const lines=(last.consolidated||{}).lines||[];const out=['post;mängd;enhet;status',...lines.map(x=>[x.designation||x.code||x.key||'',x.quantity??'',x.unit||'',x.status||''].join(';'))].join('\n');const url=URL.createObjectURL(new Blob(['\ufeff'+out],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='crow-vent-kalkyl.csv';a.click();URL.revokeObjectURL(url)};init();
</script></body></html>'''
