# ruff: noqa: E501
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from crow_ovk import EvidenceOrigin, FindingSeverity
from crow_ovk_field import (
    FieldFinding,
    FieldInspectionData,
    FieldRoom,
    FieldUnit,
    OvkPhotoEvidence,
    PhotoSyncStatus,
    UnitKind,
    load_defect_types,
    validate_field_data,
)


def ovk_field_router() -> APIRouter:
    router = APIRouter()

    @router.get("/ovk/falt", response_class=HTMLResponse)
    def field_page() -> str:
        return _FIELD_HTML

    @router.get("/api/ovk/field/defect-types", response_model=None)
    def defect_types() -> dict[str, Any]:
        return {
            "defect_types": [
                {
                    "id": item.defect_id,
                    "label": item.label,
                    "description": item.description,
                    "default_rule_refs": list(item.default_rule_refs),
                }
                for item in load_defect_types()
            ]
        }

    @router.post("/api/ovk/field/validate", response_model=None)
    async def validate_field_payload(request: Request) -> dict[str, Any]:
        payload: Any = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_FIELD_DATA"})
        try:
            data = _field_data_from_payload(payload)
            validate_field_data(data)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_OVK_FIELD_DATA", "message": str(exc)},
            ) from exc
        return {
            "inspection_id": data.inspection_id,
            "units": len(data.units),
            "rooms": len(data.rooms),
            "findings": len(data.findings),
            "photos": len(data.photos),
            "valid": True,
        }

    return router


def _field_data_from_payload(payload: dict[str, Any]) -> FieldInspectionData:
    inspection_id = str(payload["inspection_id"])
    units = tuple(
        FieldUnit(
            unit_id=str(item["unit_id"]),
            inspection_id=inspection_id,
            number=str(item["number"]),
            kind=UnitKind(str(item.get("kind", "apartment"))),
            label=str(item.get("label", "")),
        )
        for item in _dict_items(payload.get("units", []), "units")
    )
    rooms = tuple(
        FieldRoom(
            room_id=str(item["room_id"]),
            unit_id=str(item["unit_id"]),
            name=str(item["name"]),
        )
        for item in _dict_items(payload.get("rooms", []), "rooms")
    )
    findings = tuple(
        FieldFinding(
            finding_id=str(item["finding_id"]),
            inspection_id=inspection_id,
            unit_id=str(item["unit_id"]),
            defect_type=str(item["defect_type"]),
            description=str(item.get("description", "")),
            severity=FindingSeverity(str(item.get("severity", "info"))),
            room_id=_optional_str(item.get("room_id")),
            checkpoint_id=_optional_str(item.get("checkpoint_id")),
            system_id=_optional_str(item.get("system_id")),
            rule_refs=tuple(str(value) for value in item.get("rule_refs", [])),
            origin=EvidenceOrigin(str(item.get("origin", "observed"))),
        )
        for item in _dict_items(payload.get("findings", []), "findings")
    )
    photos = tuple(
        OvkPhotoEvidence(
            photo_id=str(item["photo_id"]),
            inspection_id=inspection_id,
            unit_id=str(item["unit_id"]),
            unit_number=str(item["unit_number"]),
            defect_type=str(item["defect_type"]),
            captured_at=str(item["captured_at"]),
            captured_by=str(item["captured_by"]),
            local_uri=str(item["local_uri"]),
            sha256=str(item["sha256"]),
            mime_type=str(item["mime_type"]),
            room_id=_optional_str(item.get("room_id")),
            finding_id=_optional_str(item.get("finding_id")),
            checkpoint_id=_optional_str(item.get("checkpoint_id")),
            system_id=_optional_str(item.get("system_id")),
            description=str(item.get("description", "")),
            rule_refs=tuple(str(value) for value in item.get("rule_refs", [])),
            sync_status=PhotoSyncStatus(str(item.get("sync_status", "local"))),
        )
        for item in _dict_items(payload.get("photos", []), "photos")
    )
    return FieldInspectionData(
        inspection_id=inspection_id,
        units=units,
        rooms=rooms,
        findings=findings,
        photos=photos,
    )


def _dict_items(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TypeError(f"{name} must be a list of objects")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


_FIELD_HTML = r'''<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Crow OVK Fält</title>
<style>:root{font-family:Inter,system-ui,sans-serif;color:#16202a;background:#eef2f4}*{box-sizing:border-box}body{margin:0}.top{position:sticky;top:0;z-index:5;background:#17202a;color:#fff;padding:12px 16px;display:flex;justify-content:space-between;align-items:center}.top a{color:#fff}.wrap{max-width:760px;margin:auto;padding:14px}.card{background:#fff;border:1px solid #d8e0e6;border-radius:14px;padding:16px;margin-bottom:12px}.step{font-size:12px;font-weight:800;letter-spacing:.08em;color:#607080}.big{font-size:24px;margin:4px 0 12px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}label{display:block;font-size:13px;font-weight:700;margin:10px 0 5px}input,select,textarea,button{width:100%;font:inherit;border-radius:10px}input,select,textarea{padding:13px;border:1px solid #bcc8d1;background:#fff}textarea{min-height:90px}.btn{border:0;padding:15px;font-weight:800;cursor:pointer;background:#17202a;color:#fff;margin-top:10px}.btn.alt{background:#fff;color:#17202a;border:1px solid #aeb9c3}.btn.good{background:#176b3a}.pill{display:inline-block;padding:5px 9px;border-radius:999px;background:#edf1f4;font-size:12px}.list{display:grid;gap:8px}.item{border:1px solid #dce3e8;border-radius:10px;padding:12px}.hidden{display:none}.status{padding:12px;border-radius:10px;background:#edf1f4;margin-top:10px}.warn{background:#fff2cc}.preview{max-width:100%;max-height:260px;border-radius:10px;margin-top:10px}.footer{position:sticky;bottom:0;background:rgba(238,242,244,.96);padding:10px 14px calc(10px + env(safe-area-inset-bottom));border-top:1px solid #d6dee4}.footer .grid{max-width:760px;margin:auto}@media(max-width:520px){.grid{grid-template-columns:1fr}.big{font-size:21px}.wrap{padding:10px}}</style></head>
<body><header class="top"><strong>Crow OVK · Fält</strong><a href="/ovk/besiktning">Workbench</a></header><main class="wrap"><section class="card"><div class="step">1 · BESIKTNING</div><h1 class="big">Välj arbetsyta</h1><div class="grid"><div><label>Projekt</label><select id="project"><option value="adhoc">Ad hoc</option></select></div><div><label>Besiktnings-ID</label><input id="inspection" value="ovk-001"></div></div><label>Besiktningsman</label><input id="inspector" placeholder="Namn"><button class="btn" id="start">Starta fältläge</button></section>
<section class="card hidden" id="unitCard"><div class="step">2 · LÄGENHET / LOKAL</div><h2 class="big">Var är du?</h2><div class="grid"><div><label>Typ</label><select id="kind"><option value="apartment">Lägenhet</option><option value="premises">Lokal</option></select></div><div><label>Nummer</label><input id="unitNumber" inputmode="numeric" placeholder="1203"></div></div><label>Benämning</label><input id="unitLabel" placeholder="Valfri"><button class="btn" id="setUnit">Öppna enhet</button></section>
<section class="card hidden" id="roomCard"><div class="step">3 · RUM</div><h2 class="big"><span id="unitHeading"></span></h2><label>Rum</label><input id="roomName" placeholder="Badrum, kök, sovrum..."><button class="btn" id="setRoom">Öppna rum</button></section>
<section class="card hidden" id="findingCard"><div class="step">4 · KONTROLL / FEL</div><h2 class="big" id="roomHeading"></h2><label>Feltyp</label><select id="defect"></select><label>Beskrivning</label><textarea id="description" placeholder="Vad observerades?"></textarea><div class="grid"><div><label>Allvarlighetsgrad</label><select id="severity"><option value="info">Information</option><option value="minor">Mindre</option><option value="major">Större</option></select></div><div><label>System-ID</label><input id="system" placeholder="FTX01"></div></div><button class="btn" id="addFinding">Registrera fel</button><div id="ruleInfo" class="status"></div></section>
<section class="card hidden" id="photoCard"><div class="step">5 · FOTO</div><h2 class="big">Dokumentera</h2><p>Bildens lägenhets-/lokalnummer och feltyp ärvs automatiskt från aktivt fel.</p><input id="photo" type="file" accept="image/*" capture="environment"><img id="preview" class="preview hidden" alt="Förhandsvisning"><button class="btn" id="addPhoto" disabled>Lägg bilden till felet</button><div id="photoStatus" class="status">Ingen bild vald.</div></section>
<section class="card"><div class="step">FÄLTDATA</div><div class="grid"><div class="item"><span>Enheter</span><strong id="unitCount">0</strong></div><div class="item"><span>Fel</span><strong id="findingCount">0</strong></div></div><div class="list" id="findings"></div><button class="btn alt" id="validate">Validera mot Crow</button><div id="validation" class="status">Inte validerad.</div></section></main>
<div class="footer"><div class="grid"><button class="btn alt" onclick="history.back()">Tillbaka</button><button class="btn good" id="nextUnit">Nästa lägenhet/lokal</button></div></div>
<script>const $=id=>document.getElementById(id);const state={inspection_id:'',units:[],rooms:[],findings:[],photos:[],unit:null,room:null,finding:null,file:null,defects:[]};const uid=p=>p+'-'+crypto.randomUUID();async function init(){const m=await fetch('/api/me/modules');if(m.ok){const d=await m.json();if(!(d.modules||[]).some(x=>x.id==='ovk')){$('validation').textContent='OVK ingår inte i licensen.';$('start').disabled=true;return}}const r=await fetch('/api/ovk/field/defect-types');if(r.ok){const d=await r.json();state.defects=d.defect_types||[];$('defect').innerHTML=state.defects.map(x=>'<option value="'+x.id+'">'+x.label+'</option>').join('');showRule()}const p=await fetch('/api/projects');if(p.ok){for(const x of await p.json()){const o=document.createElement('option');o.value=x.project_id;o.textContent=x.project_name||x.name||x.project_id;$('project').appendChild(o)}}}function show(id){$(id).classList.remove('hidden')}function showRule(){const d=state.defects.find(x=>x.id===$('defect').value);$('ruleInfo').textContent=d&&d.default_rule_refs.length?'Referenser: '+d.default_rule_refs.join(', '):'Ingen automatisk regelhänvisning. Bedömning görs separat.'}function render(){ $('unitCount').textContent=state.units.length;$('findingCount').textContent=state.findings.length;$('findings').innerHTML=state.findings.map(f=>'<div class="item"><strong>'+esc(f.unit_number)+' · '+esc(f.defect_type)+'</strong><br>'+esc(f.description)+'<br><span class="pill">'+esc(f.room_name||'utan rum')+'</span> <span class="pill">bilder '+state.photos.filter(p=>p.finding_id===f.finding_id).length+'</span></div>').join('')}function esc(v){const d=document.createElement('div');d.textContent=v||'';return d.innerHTML}$('start').onclick=()=>{state.inspection_id=$('inspection').value.trim();if(!state.inspection_id||!$('inspector').value.trim()){alert('Besiktnings-ID och besiktningsman krävs.');return}show('unitCard')};$('setUnit').onclick=()=>{const n=$('unitNumber').value.trim();if(!n){alert('Lägenhets-/lokalnummer krävs.');return}const u={unit_id:uid('unit'),inspection_id:state.inspection_id,number:n,kind:$('kind').value,label:$('unitLabel').value.trim()};state.units.push(u);state.unit=u;state.room=null;state.finding=null;$('unitHeading').textContent=($('kind').value==='apartment'?'Lgh ':'Lokal ')+n;show('roomCard');render()};$('setRoom').onclick=()=>{if(!state.unit)return;const n=$('roomName').value.trim();if(!n){alert('Rumsnamn krävs.');return}const r={room_id:uid('room'),unit_id:state.unit.unit_id,name:n};state.rooms.push(r);state.room=r;$('roomHeading').textContent=state.unit.number+' · '+n;show('findingCard')};$('defect').onchange=showRule;$('addFinding').onclick=()=>{if(!state.unit||!state.room)return;const dt=state.defects.find(x=>x.id===$('defect').value);const f={finding_id:uid('finding'),inspection_id:state.inspection_id,unit_id:state.unit.unit_id,unit_number:state.unit.number,room_id:state.room.room_id,room_name:state.room.name,defect_type:$('defect').value,description:$('description').value.trim(),severity:$('severity').value,system_id:$('system').value.trim()||null,rule_refs:dt?dt.default_rule_refs:[],origin:'observed'};state.findings.push(f);state.finding=f;show('photoCard');render()};$('photo').onchange=async e=>{const f=e.target.files&&e.target.files[0];state.file=f||null;$('addPhoto').disabled=!f;if(f){$('preview').src=URL.createObjectURL(f);show('preview');$('photoStatus').textContent=f.name+' · '+Math.round(f.size/1024)+' kB'}};$('addPhoto').onclick=async()=>{if(!state.file||!state.finding||!state.unit)return;const b=await state.file.arrayBuffer();const h=await crypto.subtle.digest('SHA-256',b);const sha=[...new Uint8Array(h)].map(x=>x.toString(16).padStart(2,'0')).join('');state.photos.push({photo_id:uid('photo'),inspection_id:state.inspection_id,unit_id:state.unit.unit_id,unit_number:state.unit.number,defect_type:state.finding.defect_type,captured_at:new Date().toISOString(),captured_by:$('inspector').value.trim(),local_uri:'browser-session:'+state.file.name,sha256:sha,mime_type:state.file.type||'image/jpeg',room_id:state.finding.room_id,finding_id:state.finding.finding_id,checkpoint_id:null,system_id:state.finding.system_id,description:state.finding.description,rule_refs:state.finding.rule_refs,sync_status:'local'});$('photoStatus').textContent='Bildmetadata registrerad i denna session. Binärfilen synkas först i kommande offline/media-pass.';render()};$('validate').onclick=async()=>{const payload={inspection_id:state.inspection_id,units:state.units,rooms:state.rooms,findings:state.findings.map(({unit_number,room_name,...f})=>f),photos:state.photos};const r=await fetch('/api/ovk/field/validate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();$('validation').className='status '+(r.ok?'':'warn');$('validation').textContent=r.ok?'Validerad: '+d.units+' enheter, '+d.findings+' fel, '+d.photos+' bilder.':'Fel: '+JSON.stringify(d)};$('nextUnit').onclick=()=>{state.unit=null;state.room=null;state.finding=null;$('unitNumber').value='';$('unitLabel').value='';$('roomName').value='';$('description').value='';show('unitCard');window.scrollTo({top:$('unitCard').offsetTop-70,behavior:'smooth'})};init();</script></body></html>'''
