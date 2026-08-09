# ruff: noqa: E501
from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from crow_vent_quote import VentQuoteRequest, build_vent_quote, quote_to_payload


def vent_quote_router() -> APIRouter:
    router = APIRouter()

    @router.get("/vent/offert", response_class=HTMLResponse)
    def vent_quote_page() -> str:
        return _QUOTE_HTML

    @router.post("/api/vent/projects/{project_id}/quote", response_model=None)
    async def vent_quote(project_id: str, request: Request) -> JSONResponse:
        payload: Any = await request.json()
        takeoff_input = dict(payload.get("takeoff", {}))
        quote_input = dict(payload.get("quote", {}))

        transport = httpx.ASGITransport(app=request.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://crow.internal",
        ) as client:
            response = await client.post(
                f"/api/vent/projects/{project_id}/takeoff",
                json=takeoff_input,
            )
        if response.status_code != 200:
            return JSONResponse(status_code=response.status_code, content=response.json())

        priced = response.json().get("priced")
        if priced is None:
            return JSONResponse(
                status_code=422,
                content={"detail": {"code": "PRICED_TAKEOFF_REQUIRED"}},
            )

        try:
            quote_request = VentQuoteRequest(
                project_name=str(quote_input.get("project_name", project_id)),
                customer_name=str(quote_input.get("customer_name", "")),
                quote_date=str(quote_input.get("quote_date", "")),
                validity_days=int(quote_input.get("validity_days", 30)),
                overhead_percent=Decimal(str(quote_input.get("overhead_percent", "0"))),
                risk_percent=Decimal(str(quote_input.get("risk_percent", "0"))),
                profit_percent=Decimal(str(quote_input.get("profit_percent", "0"))),
                scope_note=str(quote_input.get("scope_note", "")),
                exclusions=tuple(str(item) for item in quote_input.get("exclusions", [])),
            )
            quote = build_vent_quote(priced, quote_request)
        except (TypeError, ValueError) as error:
            return JSONResponse(
                status_code=422,
                content={"detail": {"code": "INVALID_QUOTE_INPUT", "message": str(error)}},
            )
        return JSONResponse(content=quote_to_payload(quote))

    return router


_QUOTE_HTML = r'''<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Crow Vent – Offert</title>
<style>
:root{font-family:Inter,system-ui,sans-serif;color:#18212b;background:#f4f6f8}body{margin:0}.shell{display:grid;grid-template-columns:230px 1fr;min-height:100vh}aside{background:#17202a;color:#fff;padding:24px}aside h1{font-size:20px;margin:0 0 28px}nav a{display:block;color:#dce5ed;text-decoration:none;padding:10px 0}nav a.active{font-weight:700;color:#fff}main{padding:32px;max-width:1200px}.eyebrow{font-size:12px;letter-spacing:.12em;color:#687684}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{background:#fff;border:1px solid #dfe5ea;border-radius:10px;padding:20px}label{display:block;font-size:13px;font-weight:600;margin:12px 0 5px}input,select,textarea{width:100%;box-sizing:border-box;padding:9px;border:1px solid #cbd4dc;border-radius:6px}textarea{min-height:95px;font-family:ui-monospace,monospace}.three{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.actions{display:flex;gap:8px;margin-top:14px}button{padding:10px 14px;border:0;border-radius:6px;cursor:pointer}button.primary{background:#17202a;color:#fff}.status{padding:10px;border-radius:6px;background:#eef2f5;margin-top:12px}.quote h3{margin:0}.total{font-size:32px;font-weight:700;margin:16px 0}.warning{background:#fff4d6;padding:10px;border-radius:6px}.ok{background:#e9f7ef;padding:10px;border-radius:6px}@media(max-width:800px){.shell{grid-template-columns:1fr}aside{display:none}.grid,.three{grid-template-columns:1fr}}@media print{aside,.input-panel,.actions{display:none!important}.shell{display:block}main{padding:0}.panel{border:0}}
</style></head><body><div class="shell"><aside><h1>Crow</h1><nav><a href="/">Projekt</a><a href="/vent">Ventilation</a><a class="active" href="/vent/offert">Offert</a><a href="#">Provtryckning</a><a href="#">OVK</a></nav></aside><main><p class="eyebrow">VENTILATION</p><h2>Offert</h2><p>Offertpris byggs deterministiskt ovanpå Vent-kalkylens självkostnad. Alla påslag anges explicit.</p><div class="grid"><section class="panel input-panel"><label>Projekt</label><select id="project"><option value="adhoc">Ad hoc</option></select><label>Mängdförteckning</label><textarea id="table" placeholder="T-125;132;m\nTD1;24;st"></textarea><label>Beskrivningstext</label><textarea id="text" placeholder="24 st TD1"></textarea><label>Prisbok (JSON)</label><textarea id="prices" placeholder='{"labour_rate_per_hour":520,"entries":[]}'></textarea><label>Kund</label><input id="customer"><label>Offertdatum</label><input id="date" type="date"><label>Giltighet dagar</label><input id="validity" type="number" value="30" min="1"><div class="three"><div><label>Omkostnad %</label><input id="overhead" type="number" value="0" min="0" step="0.1"></div><div><label>Risk %</label><input id="risk" type="number" value="0" min="0" step="0.1"></div><div><label>Vinst %</label><input id="profit" type="number" value="0" min="0" step="0.1"></div></div><label>Omfattning</label><textarea id="scope"></textarea><label>Undantag, en per rad</label><textarea id="exclusions"></textarea><div class="actions"><button class="primary" id="run">Skapa offert</button></div><div id="status" class="status">Klar för indata.</div></section><section class="panel quote"><h3 id="title">Offertutkast</h3><p id="recipient"></p><div id="ready"></div><div class="total" id="total">—</div><div id="breakdown"></div><p id="meta"></p><p id="scopeOut"></p><div id="exclusionsOut"></div><div class="actions"><button id="print" disabled>Skriv ut / PDF</button><button id="csv" disabled>Exportera CSV</button></div></section></div></main></div>
<script>
let last=null;const $=id=>document.getElementById(id);$('date').value=new Date().toISOString().slice(0,10);
async function init(){const modules=await fetch('/api/me/modules');if(!modules.ok)return;const data=await modules.json();if(!(data.modules||[]).some(m=>m.id==='vent')){$('status').textContent='Vent ingår inte i licensen.';$('run').disabled=true;return}const projects=await fetch('/api/projects');if(projects.ok){for(const p of await projects.json()){const o=document.createElement('option');o.value=p.project_id;o.textContent=p.project_name||p.project_id;$('project').appendChild(o)}}}
function tableRows(){return $('table').value.split(/\n/).map(x=>x.trim()).filter(Boolean).map(x=>x.split(';').map(v=>v.trim()))}function lines(id){return $(id).value.split(/\n/).map(x=>x.trim()).filter(Boolean)}
$('run').onclick=async()=>{let book=null;try{book=$('prices').value.trim()?JSON.parse($('prices').value):null}catch(e){$('status').textContent='Ogiltig prisbok-JSON.';return}const takeoff={table_rows:tableRows(),text_segments:$('text').value.trim()?[$('text').value.trim()]:[]};if(book)takeoff.price_book=book;const quote={project_name:$('project').selectedOptions[0].textContent,customer_name:$('customer').value,quote_date:$('date').value,validity_days:Number($('validity').value),overhead_percent:$('overhead').value,risk_percent:$('risk').value,profit_percent:$('profit').value,scope_note:$('scope').value,exclusions:lines('exclusions')};$('status').textContent='Bygger offert…';const r=await fetch('/api/vent/projects/'+encodeURIComponent($('project').value)+'/quote',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({takeoff,quote})});const data=await r.json();if(!r.ok){$('status').textContent='Offertfel: '+JSON.stringify(data);return}last=data;render(data);$('print').disabled=false;$('csv').disabled=false;$('status').textContent='Offertutkast skapat.'};
function render(q){$('title').textContent='Offert – '+q.project_name;$('recipient').textContent=q.customer_name?('Till: '+q.customer_name):'';$('total').textContent=q.offer_total+' '+q.currency;$('ready').innerHTML=q.ready_to_send?'<div class="ok">Sändklar: inga oprissatta eller olösta poster.</div>':'<div class="warning">UTKAST: '+q.unpriced_line_count+' oprissatta och '+q.reservation_count+' reserverade poster måste hanteras.</div>';$('breakdown').innerHTML='<p>Självkostnad: '+q.base_cost+' '+q.currency+'</p><p>Omkostnad '+q.overhead_percent+' %: '+q.overhead_amount+'</p><p>Risk '+q.risk_percent+' %: '+q.risk_amount+'</p><p>Vinst '+q.profit_percent+' %: '+q.profit_amount+'</p>';$('meta').textContent='Datum '+q.quote_date+' · giltig '+q.validity_days+' dagar · prisbok '+q.source_price_book_id;$('scopeOut').textContent=q.scope_note?('Omfattning: '+q.scope_note):'';$('exclusionsOut').innerHTML=q.exclusions.length?'<h4>Undantag</h4><ul>'+q.exclusions.map(x=>'<li>'+x+'</li>').join('')+'</ul>':''}
$('print').onclick=()=>window.print();$('csv').onclick=()=>{if(!last)return;const q=last;const rows=[['fält','värde'],['projekt',q.project_name],['kund',q.customer_name],['självkostnad',q.base_cost],['omkostnad',q.overhead_amount],['risk',q.risk_amount],['vinst',q.profit_amount],['offertpris',q.offer_total],['valuta',q.currency],['sändklar',q.ready_to_send]];const out=rows.map(r=>r.join(';')).join('\n');const url=URL.createObjectURL(new Blob(['\ufeff'+out],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='crow-vent-offert.csv';a.click();URL.revokeObjectURL(url)};init();
</script></body></html>'''
