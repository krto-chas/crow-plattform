# ruff: noqa: E501
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from crow_pressure_test import ClaimOrigin, TightnessClass, load_knowledge
from crow_pressure_test.workflow import (
    RequirementProvenance,
    evaluate_pressure_test,
    evaluation_to_payload,
)


def pressure_test_router() -> APIRouter:
    router = APIRouter()

    @router.get("/provtryckning", response_class=HTMLResponse)
    def pressure_test_page() -> str:
        return _PRESSURE_TEST_HTML

    @router.post("/api/provtryckning/projects/{project_id}/evaluate", response_model=None)
    async def evaluate(project_id: str, request: Request) -> dict[str, Any]:
        payload: Any = await request.json()
        try:
            tightness_class = TightnessClass(str(payload["tightness_class"]))
            pressure_pa = int(payload["pressure_pa"])
            duct_area_m2 = Decimal(str(payload["duct_area_m2"]))
            measured_raw = payload.get("measured_leakage_lps")
            measured = None if measured_raw in (None, "") else Decimal(str(measured_raw))
            tightness_origin = ClaimOrigin(str(payload.get("tightness_origin", "stated")))
            pressure_origin = ClaimOrigin(str(payload.get("pressure_origin", "stated")))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_PRESSURE_TEST_INPUT"}) from exc

        provenance = [
            RequirementProvenance(
                field="tightness_class",
                value=tightness_class.value,
                origin=tightness_origin,
                source_ref=_optional_text(payload.get("tightness_source_ref")),
                confirmed=_confirmed(payload, "tightness_confirmed", tightness_origin),
            ),
            RequirementProvenance(
                field="pressure_pa",
                value=str(pressure_pa),
                origin=pressure_origin,
                source_ref=_optional_text(payload.get("pressure_source_ref")),
                confirmed=_confirmed(payload, "pressure_confirmed", pressure_origin),
            ),
        ]
        if bool(payload.get("pre_pour_inferred")):
            provenance.append(
                RequirementProvenance(
                    field="pre_pour_test",
                    value="provning före ingjutning",
                    origin=ClaimOrigin.INFERRED,
                    source_ref=_optional_text(payload.get("pre_pour_source_ref")),
                    confirmed=bool(payload.get("pre_pour_confirmed")),
                )
            )

        try:
            result = evaluate_pressure_test(
                project_id=project_id,
                tightness_class=tightness_class,
                pressure_pa=pressure_pa,
                duct_area_m2=duct_area_m2,
                measured_leakage_lps=measured,
                provenance=tuple(provenance),
                knowledge=load_knowledge(),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_PRESSURE_TEST_INPUT", "message": str(exc)},
            ) from exc
        return evaluation_to_payload(result)

    return router


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _confirmed(payload: dict[str, Any], key: str, origin: ClaimOrigin) -> bool:
    if origin is ClaimOrigin.STATED:
        return True
    return bool(payload.get(key))


_PRESSURE_TEST_HTML = r'''<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Crow Provtryckning</title>
<style>
:root{font-family:Inter,system-ui,sans-serif;color:#18212b;background:#f4f6f8}body{margin:0}.shell{display:grid;grid-template-columns:230px 1fr;min-height:100vh}aside{background:#17202a;color:#fff;padding:24px}aside h1{font-size:20px;margin:0 0 28px}nav a{display:block;color:#dce5ed;text-decoration:none;padding:10px 0}nav a.active{font-weight:700;color:#fff}main{padding:32px;max-width:1200px}.eyebrow{font-size:12px;letter-spacing:.12em;color:#687684}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{background:#fff;border:1px solid #dfe5ea;border-radius:10px;padding:20px}label{display:block;font-size:13px;font-weight:600;margin:12px 0 5px}select,input{width:100%;box-sizing:border-box;padding:9px;border:1px solid #cbd4dc;border-radius:6px}.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}.checkbox{display:flex;gap:8px;align-items:center;margin-top:12px}.checkbox input{width:auto}.primary{margin-top:16px;padding:10px 14px;border:0;border-radius:6px;background:#17202a;color:#fff;cursor:pointer}.status{padding:12px;border-radius:6px;background:#eef2f5;margin-top:12px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{background:#f5f7f9;padding:12px;border-radius:6px}.metric strong{display:block;font-size:18px}.pass{background:#e5f6ea}.fail{background:#fdeaea}.warning{background:#fff4cf}.prov{margin-top:14px}.prov-item{border-top:1px solid #e6eaee;padding:10px 0}.badge{display:inline-block;padding:3px 7px;border-radius:12px;background:#e8edf1;font-size:11px;font-weight:700}.badge.inferred{background:#fff0bd}.standards{font-size:13px;color:#52616f}@media(max-width:800px){.shell{grid-template-columns:1fr}aside{display:none}.grid,.metrics,.two{grid-template-columns:1fr}}
</style></head><body><div class="shell"><aside><h1>Crow</h1><nav><a href="/">Projekt</a><a href="/vent">Ventilation</a><a class="active" href="/provtryckning">Provtryckning</a><a href="#">OVK</a></nav></aside><main><p class="eyebrow">PROVTRYCKNING</p><h2>Täthetsprovning</h2><p>Beräkning och mätresultat med synlig STATED/INFERRED-proveniens.</p><div class="grid"><section class="panel"><label>Projekt</label><select id="project"><option value="adhoc">Ad hoc</option></select><div class="two"><div><label>Täthetsklass</label><select id="tightness"><option>A</option><option>B</option><option selected>C</option><option>D</option></select></div><div><label>Proveniens</label><select id="tightnessOrigin"><option value="stated">STATED</option><option value="inferred">INFERRED</option></select></div></div><label>Källreferens täthetsklass</label><input id="tightnessSource" placeholder="Handling/sida/rad"><label class="checkbox"><input type="checkbox" id="tightnessConfirmed">Bekräfta INFERRED täthetsklass</label><div class="two"><div><label>Provtryck [Pa]</label><input id="pressure" type="number" value="400"></div><div><label>Proveniens</label><select id="pressureOrigin"><option value="stated">STATED</option><option value="inferred">INFERRED</option></select></div></div><label>Källreferens provtryck</label><input id="pressureSource" placeholder="Handling/sida/rad"><label class="checkbox"><input type="checkbox" id="pressureConfirmed">Bekräfta INFERRED provtryck</label><div class="two"><div><label>Kanalarea [m²]</label><input id="area" inputmode="decimal" value="10"></div><div><label>Uppmätt läckage [l/s]</label><input id="measured" inputmode="decimal" placeholder="lämna tomt före mätning"></div></div><label class="checkbox"><input type="checkbox" id="prePour">INFERRED: provning före ingjutning</label><label class="checkbox"><input type="checkbox" id="prePourConfirmed">Bekräfta antagandet om prov före ingjutning</label><button class="primary" id="evaluate">Beräkna / bedöm</button><div id="message" class="status">Klar för indata.</div></section><section class="panel"><div id="metrics" class="metrics"></div><div id="protocolStatus" class="status">Ingen bedömning ännu.</div><div class="prov"><h3>Proveniens</h3><div id="provenance"></div></div><div class="standards"><h3>Kunskapsreferenser</h3><div id="standards"></div></div></section></div></main></div>
<script>
const $=id=>document.getElementById(id);
async function init(){const modules=await fetch('/api/me/modules');if(!modules.ok){$('message').textContent='Provtryckning är inte tillgänglig: '+modules.status;return}const data=await modules.json();if(!(data.modules||[]).some(m=>m.id==='provtryckning')){$('message').textContent='Provtryckning ingår inte i licensen.';$('evaluate').disabled=true;return}const projects=await fetch('/api/projects');if(projects.ok){for(const p of await projects.json()){const o=document.createElement('option');o.value=p.project_id;o.textContent=p.project_name||p.project_id;$('project').appendChild(o)}}}
$('evaluate').onclick=async()=>{const body={tightness_class:$('tightness').value,tightness_origin:$('tightnessOrigin').value,tightness_source_ref:$('tightnessSource').value,tightness_confirmed:$('tightnessConfirmed').checked,pressure_pa:$('pressure').value,pressure_origin:$('pressureOrigin').value,pressure_source_ref:$('pressureSource').value,pressure_confirmed:$('pressureConfirmed').checked,duct_area_m2:$('area').value,measured_leakage_lps:$('measured').value,pre_pour_inferred:$('prePour').checked,pre_pour_confirmed:$('prePourConfirmed').checked};$('message').textContent='Beräknar…';const r=await fetch('/api/provtryckning/projects/'+encodeURIComponent($('project').value)+'/evaluate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok){$('message').textContent='Fel: '+JSON.stringify(data);return}render(data)};
function render(d){const measured=d.measured_leakage_lps===null?'—':d.measured_leakage_lps+' l/s';$('metrics').innerHTML=[['Tillåtet',d.allowed_leakage_lps+' l/s'],['Uppmätt',measured],['Resultat',d.status.toUpperCase()]].map(x=>'<div class="metric"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join('');const ps=$('protocolStatus');ps.className='status '+(d.ready_for_protocol?'pass':'warning');ps.textContent=d.ready_for_protocol?'Resultatet är protokollklart.':'Protokoll blockerat: mätning saknas eller INFERRED-krav är obekräftade.';$('provenance').innerHTML=(d.provenance||[]).map(p=>'<div class="prov-item"><span class="badge '+(p.origin==='inferred'?'inferred':'')+'">'+p.origin.toUpperCase()+'</span> <strong>'+p.field+'</strong>: '+p.value+(p.source_ref?' · '+p.source_ref:'')+(p.requires_confirmation?' · BEKRÄFTELSE KRÄVS':'')+'</div>').join('');$('standards').innerHTML=(d.standards||[]).map(s=>'<div>'+s.id+' — '+s.title+'</div>').join('');$('message').className='status '+(d.status==='pass'?'pass':d.status==='fail'?'fail':'');$('message').textContent='Bedömning klar. ATC: '+d.atc_class}
init();
</script></body></html>'''
