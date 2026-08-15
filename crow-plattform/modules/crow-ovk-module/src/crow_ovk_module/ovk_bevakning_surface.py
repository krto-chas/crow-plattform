# ruff: noqa: E501
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from crow_ovk_besiktningsbevakning import build_watchlist, watchlist_to_payload
from crow_ovk_intyg import OvkIntygRepository
from crow_ovk_workflow import OvkReinspectionRepository


def ovk_bevakning_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    intyg_repository = OvkIntygRepository(data_root)
    case_repository = OvkReinspectionRepository(data_root)

    @router.get("/ovk/bevakning", response_class=HTMLResponse)
    def bevakning_page() -> str:
        return _BEVAKNING_HTML

    @router.get("/api/ovk/projects/{project_id}/bevakning", response_model=None)
    def get_watchlist(
        project_id: str,
        window_days: int = Query(default=180, ge=0, le=3650),
        today: str | None = Query(default=None),
    ) -> dict[str, Any]:
        try:
            anchor = date.fromisoformat(today) if today else date.today()
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_OVK_BEVAKNING", "message": f"invalid date {today!r}"},
            ) from exc
        try:
            intyg = intyg_repository.list(project_id)
            cases = case_repository.list(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_PROJECT"}) from exc
        watchlist = build_watchlist(
            project_id=project_id,
            intyg=intyg,
            cases=cases,
            today=anchor,
            reminder_window_days=window_days,
        )
        return watchlist_to_payload(watchlist)

    return router


_BEVAKNING_HTML = r"""<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Crow OVK Bevakning</title>
<style>:root{font-family:Inter,system-ui,sans-serif;color:#18212b;background:#f4f6f8}*{box-sizing:border-box}body{margin:0}.shell{display:grid;grid-template-columns:230px 1fr;min-height:100vh}aside{background:#17202a;color:#fff;padding:24px}nav a{display:block;color:#dce5ed;text-decoration:none;padding:10px 0}nav a.active{font-weight:700;color:#fff}main{padding:32px;max-width:1200px}.panel{background:#fff;border:1px solid #dfe5ea;border-radius:10px;padding:20px;margin-top:16px}label{display:block;font-size:13px;font-weight:600;margin:10px 0 4px}input,select{padding:8px;border:1px solid #cbd4dc;border-radius:6px}.controls{display:flex;gap:12px;align-items:end;flex-wrap:wrap}.primary{padding:10px 14px;border-radius:6px;cursor:pointer;border:0;background:#17202a;color:#fff}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}.metric{background:#f5f7f9;padding:12px;border-radius:6px}.metric strong{display:block;font-size:20px}.item{border:1px solid #dfe5ea;border-left-width:5px;border-radius:8px;padding:12px;margin-top:10px}.item.forsenad,.item.ombesiktning_kravs{border-left-color:#8f2020;background:#fdf4f4}.item.paminnelse{border-left-color:#b98a00;background:#fffaef}.item.ok{border-left-color:#1c6b34}.item.ingen_frist{border-left-color:#aeb9c3}.badge{display:inline-block;padding:3px 8px;border-radius:12px;font-size:11px;font-weight:700;background:#e8edf1}.muted{font-size:12px;color:#607080}.basis{font-size:12px;color:#52616f;font-style:italic;margin-top:5px}@media(max-width:900px){.shell{grid-template-columns:1fr}aside{display:none}.summary{grid-template-columns:1fr}}</style></head>
<body><div class="shell"><aside><h2>Crow</h2><nav><a href="/">Projekt</a><a href="/vent">Ventilation</a><a href="/provtryckning">Provtryckning</a><a href="/ovk">OVK import</a><a href="/ovk/besiktning">OVK besiktning</a><a href="/ovk/falt">OVK fält</a><a href="/ovk/intyg">OVK intyg</a><a href="/ovk/ombesiktning">OVK ombesiktning</a><a class="active" href="/ovk/bevakning">OVK bevakning</a></nav></aside><main><p>OVK · BEVAKNING</p><h1>Besiktningsbevakning</h1><p>Härledd vy ur utfärdade intyg och öppna ombesiktningsärenden — kommande frister, påminnelser och förseningar per byggnad. Varje post bär sin skrivna basis.</p><div class="panel"><div class="controls"><div><label>Projekt</label><select id="project"><option value="adhoc">Ad hoc</option></select></div><div><label>Påminnelsefönster (dagar)</label><input id="window" type="number" value="180" min="0"></div><button class="primary" id="load">Hämta bevakningslista</button></div><div id="summary" class="summary"></div><div id="items"><div class="muted">Ingen lista hämtad.</div></div></div></main></div>
<script>
const $=id=>document.getElementById(id);const LABELS={forsenad:'FÖRSENAD',ombesiktning_kravs:'OMBESIKTNING KRÄVS',paminnelse:'PÅMINNELSE',ok:'OK',ingen_frist:'INGEN FRIST'};
function ensureProject(id){if(!id)return;if(![...$('project').options].some(o=>o.value===id)){const option=document.createElement('option');option.value=id;option.textContent=id;$('project').appendChild(option)}}
async function init(){const modules=await fetch('/api/me/modules');if(!modules.ok)return;const data=await modules.json();if(!(data.modules||[]).some(m=>m.id==='ovk')){$('items').textContent='OVK ingår inte i licensen.';$('load').disabled=true;return}const projects=await fetch('/api/projects');if(projects.ok){for(const p of await projects.json()){ensureProject(p.project_id);const o=[...$('project').options].find(x=>x.value===p.project_id);if(o)o.textContent=p.project_name||p.name||p.project_id}}}
$('load').onclick=async()=>{const p=$('project').value;const r=await fetch('/api/ovk/projects/'+encodeURIComponent(p)+'/bevakning?window_days='+encodeURIComponent($('window').value||'180'));const d=await r.json();if(!r.ok){$('items').textContent='Fel: '+JSON.stringify(d);return}
$('summary').innerHTML=[['Förseningar/ombesiktning',d.overdue_count],['Påminnelser',d.reminder_count],['Poster totalt',d.items.length]].map(x=>'<div class="metric"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join('');
$('items').innerHTML=d.items.length?d.items.map(item=>'<div class="item '+item.status+'"><strong>'+item.building_id+'</strong> · '+item.object_name+' <span class="badge">'+(LABELS[item.status]||item.status)+'</span><div class="muted">'+(item.source==='intyg'?'Intyg ':'Ombesiktningsärende ')+item.ref_id+' · Besiktning '+item.inspection_id+(item.due_date?' · Frist '+item.due_date+' ('+item.days_until+' dagar)':'')+(item.interval_years?' · Intervall '+item.interval_years+' år':'')+'</div><div class="basis">'+item.basis+'</div></div>').join(''):'<div class="muted">Inga bevakningsposter i projektet.</div>'};
init();
</script></body></html>"""
