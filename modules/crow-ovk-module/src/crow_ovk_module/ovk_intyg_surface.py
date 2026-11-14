# ruff: noqa: E501
from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
from typing import Any

from crow_ovk_export import intyg_pdf
from crow_ovk_fastighet import (
    BesiktningsmanRepository,
    FastighetRepository,
    funktionskontrollant_from,
)
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response

from crow_ovk_intyg import (
    Behorighet,
    Byggnadsagare,
    Funktionskontrollant,
    OvkIntyg,
    OvkIntygRepository,
    build_intyg,
    intyg_html,
    intyg_to_payload,
    intyg_verification_code,
    intyg_verify_url,
    verify_intyg_code,
)
from crow_ovk_pricing import BuildingCategory, InspectionType
from crow_ovk_workflow import OvkWorkflowRepository


def ovk_intyg_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    workflow_repository = OvkWorkflowRepository(data_root)
    intyg_repository = OvkIntygRepository(data_root)
    fastighet_repository = FastighetRepository(data_root)
    besiktningsman_repository = BesiktningsmanRepository(data_root)

    def _resolve_fastighetsbeteckning(project_id: str, payload: dict[str, Any]) -> str:
        fastighet_id = payload.get("fastighet_id")
        if isinstance(fastighet_id, str) and fastighet_id.strip():
            try:
                fastighet = fastighet_repository.load(project_id, fastighet_id.strip())
            except FileNotFoundError as exc:
                raise HTTPException(
                    status_code=404, detail={"code": "FASTIGHET_NOT_FOUND"}
                ) from exc
            return fastighet.fastighetsbeteckning
        return _required(payload, "fastighetsbeteckning")

    def _resolve_byggnadsagare(project_id: str, payload: dict[str, Any]) -> Byggnadsagare:
        fastighet_id = payload.get("fastighet_id")
        if isinstance(fastighet_id, str) and fastighet_id.strip():
            fastighet = fastighet_repository.load(project_id, fastighet_id.strip())
            if fastighet.byggnadsagare_namn.strip():
                contact_parts = [
                    part
                    for part in (
                        fastighet.byggnadsagare_adress.gata,
                        fastighet.byggnadsagare_adress.postnr,
                        fastighet.byggnadsagare_adress.ort,
                    )
                    if part.strip()
                ]
                return Byggnadsagare(
                    name=fastighet.byggnadsagare_namn,
                    contact=" ".join(contact_parts) or None,
                )
        return Byggnadsagare(
            name=_required(payload, "byggnadsagare_name"),
            contact=_optional(payload.get("byggnadsagare_contact")),
        )

    def _resolve_kontrollant(payload: dict[str, Any]) -> Funktionskontrollant:
        besiktningsman_id = payload.get("besiktningsman_id")
        if isinstance(besiktningsman_id, str) and besiktningsman_id.strip():
            try:
                person = besiktningsman_repository.load(besiktningsman_id.strip())
            except FileNotFoundError as exc:
                raise HTTPException(
                    status_code=404, detail={"code": "BESIKTNINGSMAN_NOT_FOUND"}
                ) from exc
            return funktionskontrollant_from(person)
        return Funktionskontrollant(
            name=_required(payload, "kontrollant_name"),
            behorighet=Behorighet(_required(payload, "kontrollant_behorighet")),
            certification_body=_required(payload, "kontrollant_certification_body"),
            certificate_number=_required(payload, "kontrollant_certificate_number"),
            certificate_valid_to=_optional_date(payload.get("kontrollant_certificate_valid_to")),
        )

    @router.get("/ovk/intyg", response_class=HTMLResponse)
    def intyg_page() -> str:
        return _INTYG_HTML

    @router.get("/api/ovk/projects/{project_id}/intyg", response_model=None)
    def list_intyg(project_id: str) -> dict[str, Any]:
        try:
            items = intyg_repository.list(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_PROJECT"}) from exc
        return {
            "project_id": project_id,
            "intyg": [
                {
                    "intyg_id": item.intyg_id,
                    "inspection_id": item.inspection_id,
                    "object_name": item.object_name,
                    "result": item.result.value,
                    "issued_date": item.issued_date.isoformat(),
                    "next_inspection_due": (
                        item.next_inspection.due_date.isoformat()
                        if item.next_inspection.due_date is not None
                        else None
                    ),
                }
                for item in items
            ],
        }

    @router.get("/api/ovk/projects/{project_id}/intyg/{intyg_id}", response_model=None)
    def get_intyg(project_id: str, intyg_id: str) -> dict[str, Any]:
        return intyg_to_payload(_load(intyg_repository, project_id, intyg_id))

    @router.get(
        "/api/ovk/projects/{project_id}/intyg/{intyg_id}/anslag",
        response_class=HTMLResponse,
    )
    def export_anslag(project_id: str, intyg_id: str) -> str:
        return intyg_html(_load(intyg_repository, project_id, intyg_id))

    async def _build_from_request(
        project_id: str, inspection_id: str, request: Request
    ) -> OvkIntyg:
        payload: Any = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_INTYG"})
        try:
            record = workflow_repository.load(project_id, inspection_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "OVK_INSPECTION_NOT_FOUND"}
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"}) from exc
        try:
            return build_intyg(
                intyg_id=_required(payload, "intyg_id"),
                record=record,
                fastighetsbeteckning=_resolve_fastighetsbeteckning(project_id, payload),
                byggnadsagare=_resolve_byggnadsagare(project_id, payload),
                funktionskontrollant=_resolve_kontrollant(payload),
                inspection_type=InspectionType(_required(payload, "inspection_type")),
                inspection_date=_required_date(payload, "inspection_date"),
                building_category=BuildingCategory(_required(payload, "building_category")),
                school_or_care=bool(payload.get("school_or_care", False)),
                issued_date=_optional_date(payload.get("issued_date")),
            )
        except ValueError as exc:
            message = str(exc)
            if "protocol ready" in message or "pending" in message:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "OVK_INTYG_NOT_READY",
                        "conclusion": record.inspection.conclusion.value,
                        "unresolved_review_count": record.unresolved_review_count,
                    },
                ) from exc
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_OVK_INTYG", "message": message},
            ) from exc

    @router.post(
        "/api/ovk/projects/{project_id}/inspections/{inspection_id}/intyg/preview",
        response_model=None,
    )
    async def preview_intyg(project_id: str, inspection_id: str, request: Request) -> Response:
        """Vattenstämplat utkast: bygger intyget utan att spara det."""
        intyg = await _build_from_request(project_id, inspection_id, request)
        return Response(
            content=intyg_pdf(intyg, draft=True),
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="ovk-intyg-utkast.pdf"'},
        )

    @router.get("/ovk/verifiera/{project_id}/{intyg_id}", response_class=HTMLResponse)
    def verify_page(project_id: str, intyg_id: str, c: str = Query(default="")) -> str:
        try:
            intyg = intyg_repository.load(project_id, intyg_id)
        except (FileNotFoundError, ValueError):
            return _verify_html(None, valid=False, code=c)
        valid = bool(c.strip()) and verify_intyg_code(intyg, c)
        return _verify_html(intyg, valid=valid, code=c)

    @router.post(
        "/api/ovk/projects/{project_id}/inspections/{inspection_id}/intyg",
        response_model=None,
    )
    async def create_intyg(
        project_id: str,
        inspection_id: str,
        request: Request,
    ) -> dict[str, Any]:
        intyg = await _build_from_request(project_id, inspection_id, request)
        try:
            intyg_repository.save(intyg)
        except FileExistsError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OVK_INTYG_ALREADY_EXISTS",
                    "message": "Intyget är redan utfärdat och kan inte skrivas över; "
                    "utfärda med ett nytt intygs-ID.",
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_OVK_INTYG", "message": str(exc)},
            ) from exc
        return {
            **intyg_to_payload(intyg),
            "verification_code": intyg_verification_code(intyg),
            "verify_url": intyg_verify_url(intyg),
        }

    return router


def _verify_html(intyg: OvkIntyg | None, *, valid: bool, code: str) -> str:
    head = (
        '<!doctype html><html lang="sv"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex">'
        "<title>OVK-verifiering</title>" + _VERIFY_CSS + "</head><body><main>"
        "<h1>OVK-verifiering</h1>"
    )
    if intyg is None or not valid:
        # Samma svar oavsett om intyget saknas eller koden är fel: sidan ska
        # inte avslöja vilka intygs-ID:n som finns.
        return (
            head + '<div class="verdict fail">EJ GILTIGT</div>'
            "<p>Intyget kunde inte verifieras. Kontrollera adressen och koden på "
            "intyget, eller kontakta utfärdaren.</p></main></body></html>"
        )
    rows = "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>"
        for label, value in (
            ("Intygs-ID", intyg.intyg_id),
            ("Fastighetsbeteckning", intyg.fastighetsbeteckning),
            ("Byggnad", f"{intyg.object_name} ({intyg.building_id})"),
            ("Resultat", "GODKÄND" if intyg.result.value == "godkand" else "EJ GODKÄND"),
            ("Besiktningsdatum", intyg.inspection_date.isoformat()),
            ("Utfärdat", intyg.issued_date.isoformat()),
            ("Funktionskontrollant", intyg.funktionskontrollant.name),
            (
                "Nästa besiktning senast",
                intyg.next_inspection.due_date.isoformat()
                if intyg.next_inspection.due_date is not None
                else "—",
            ),
        )
    )
    return (
        head + '<div class="verdict pass">GILTIGT INTYG</div>'
        "<p>Verifieringskod <code>" + escape(code) + "</code> "
        "stämmer mot det lagrade intyget.</p>"
        "<table>" + rows + "</table>"
        '<p class="note">Jämför uppgifterna ovan med det tryckta intyget. '
        "Avviker de är dokumentet inte giltigt.</p></main></body></html>"
    )


_VERIFY_CSS = (
    "<style>body{font-family:Georgia,serif;color:#18212b;background:#f4f6f8;margin:0}"
    "main{max-width:640px;margin:40px auto;padding:24px;background:#fff;"
    "border:1px solid #dfe5ea;border-radius:10px}"
    ".verdict{font-size:26px;font-weight:700;text-align:center;padding:14px;border:3px solid}"
    ".verdict.pass{color:#1c6b34;border-color:#1c6b34;background:#e5f6ea}"
    ".verdict.fail{color:#8f2020;border-color:#8f2020;background:#fbe9e9}"
    "table{width:100%;border-collapse:collapse;margin:14px 0}"
    "td,th{border:1px solid #8a97a3;padding:7px 9px;text-align:left;font-size:14px}"
    "th{background:#eef2f5;width:220px}code{font-size:15px}"
    ".note{font-size:12px;color:#52616f}</style>"
)


def _load(repository: OvkIntygRepository, project_id: str, intyg_id: str) -> Any:
    try:
        return repository.load(project_id, intyg_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "OVK_INTYG_NOT_FOUND"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_OVK_IDENTIFIER"}) from exc


def _required(item: dict[str, Any], key: str) -> str:
    value = _optional(item.get(key))
    if value is None:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_OVK_INTYG", "message": f"{key} is required"}
        )
    return value


def _optional(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _required_date(item: dict[str, Any], key: str) -> date:
    parsed = _optional_date(item.get(key))
    if parsed is None:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_OVK_INTYG", "message": f"{key} is required"}
        )
    return parsed


def _optional_date(value: object) -> date | None:
    text = _optional(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_OVK_INTYG", "message": f"invalid date {text!r}"},
        ) from exc


_INTYG_HTML = r"""<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Crow OVK Intyg</title>
<style>:root{font-family:Inter,system-ui,sans-serif;color:#18212b;background:#f4f6f8}*{box-sizing:border-box}body{margin:0}.shell{display:grid;grid-template-columns:230px 1fr;min-height:100vh}aside{background:#17202a;color:#fff;padding:24px}nav a{display:block;color:#dce5ed;text-decoration:none;padding:10px 0}nav a.active{font-weight:700;color:#fff}main{padding:32px;max-width:1200px}.grid{display:grid;grid-template-columns:420px 1fr;gap:18px}.panel{background:#fff;border:1px solid #dfe5ea;border-radius:10px;padding:20px}label{display:block;font-size:13px;font-weight:600;margin:10px 0 4px}input,select{width:100%;padding:8px;border:1px solid #cbd4dc;border-radius:6px}.primary,.secondary{margin-top:10px;padding:10px 14px;border-radius:6px;cursor:pointer}.primary{border:0;background:#17202a;color:#fff}.secondary{border:1px solid #aeb9c3;background:#fff}.status{margin-top:12px;padding:10px;background:#eef2f5;border-radius:6px}.warning{background:#fff4cf}.pass{background:#e5f6ea}.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}pre{white-space:pre-wrap;background:#f7f8fa;padding:12px;border-radius:6px;max-height:420px;overflow:auto}table{width:100%;border-collapse:collapse;margin-top:10px}td,th{border:1px solid #dfe5ea;padding:6px 8px;font-size:13px;text-align:left}@media(max-width:900px){.shell{grid-template-columns:1fr}aside{display:none}.grid{grid-template-columns:1fr}.two{grid-template-columns:1fr}}</style></head>
<body><div class="shell"><aside><h2>Crow</h2><nav><a href="/">Projekt</a><a href="/vent">Ventilation</a><a href="/provtryckning">Provtryckning</a><a href="/ovk">OVK import</a><a href="/ovk/besiktning">OVK besiktning</a><a href="/ovk/falt">OVK fält</a><a class="active" href="/ovk/intyg">OVK intyg</a></nav></aside><main><p>OVK · INTYG</p><h1>Utfärda OVK-intyg</h1><p>Intyget byggs ur ett sparat, protokollklart workflowrecord. Nästa besiktningsfrist härleds ur BFS 2011:16-intervall och märks som härledd uppgift med skriven basis.</p><div class="grid"><section class="panel"><label>Projekt</label><select id="project"><option value="adhoc">Ad hoc</option></select><label>Besiktnings-ID</label><input id="inspection" value="ovk-001"><label>Intygs-ID</label><input id="intyg" value="intyg-001"><label>Fastighetsbeteckning</label><input id="fastighet" placeholder="Berghällen 1:2"><label>Byggnadens ägare</label><input id="agare"><div class="two"><div><label>Besiktningstyp</label><select id="type"><option value="aterkommande">Återkommande</option><option value="forstagang">Förstagång</option></select></div><div><label>Byggnadskategori</label><select id="category"><option value="flerbostadshus">Flerbostadshus</option><option value="lokal">Lokal</option><option value="hotell">Hotell</option><option value="smahus">Småhus</option></select></div></div><div class="two"><div><label>Besiktningsdatum</label><input id="date" type="date"></div><div><label>Skola/vård</label><select id="school"><option value="false">Nej</option><option value="true">Ja</option></select></div></div><h3>Funktionskontrollant</h3><label>Namn</label><input id="kname"><div class="two"><div><label>Behörighet</label><select id="kbeh"><option value="K">K</option><option value="N">N</option></select></div><div><label>Certifikatnummer</label><input id="kcert"></div></div><label>Certifieringsorgan</label><input id="korgan" placeholder="RISE / Kiwa"><button class="secondary" id="preview">Förhandsgranska (UTKAST)</button><button class="primary" id="create">Utfärda intyg</button><button class="secondary" id="list">Lista intyg</button><button class="secondary" id="anslag">Öppna anslag</button><div id="message" class="status">Klar.</div></section><section class="panel"><h3>Intyg</h3><pre id="result">Inget intyg laddat.</pre><div id="items"></div></section></div></main></div>
<script>
const $=id=>document.getElementById(id);function esc(value){return String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))}function ensureProject(id){if(!id)return;if(![...$('project').options].some(o=>o.value===id)){const option=document.createElement('option');option.value=id;option.textContent=id;$('project').appendChild(option)}}
async function init(){const modules=await fetch('/api/me/modules');if(!modules.ok)return;const data=await modules.json();if(!(data.modules||[]).some(m=>m.id==='ovk')){$('message').textContent='OVK ingår inte i licensen.';$('create').disabled=true;return}const projects=await fetch('/api/projects');if(projects.ok){for(const p of await projects.json()){ensureProject(p.project_id);const o=[...$('project').options].find(x=>x.value===p.project_id);if(o)o.textContent=p.project_name||p.name||p.project_id}}$('date').value=new Date().toISOString().slice(0,10)}
function build(){return{intyg_id:$('intyg').value,fastighetsbeteckning:$('fastighet').value,byggnadsagare_name:$('agare').value,inspection_type:$('type').value,building_category:$('category').value,inspection_date:$('date').value,school_or_care:$('school').value==='true',kontrollant_name:$('kname').value,kontrollant_behorighet:$('kbeh').value,kontrollant_certification_body:$('korgan').value,kontrollant_certificate_number:$('kcert').value}}
$('create').onclick=async()=>{const p=$('project').value,i=$('inspection').value;const r=await fetch('/api/ovk/projects/'+encodeURIComponent(p)+'/inspections/'+encodeURIComponent(i)+'/intyg',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(build())});const d=await r.json();if(!r.ok){$('message').className='status warning';$('message').textContent='Fel: '+JSON.stringify(d);return}$('result').textContent=JSON.stringify(d,null,2);$('message').className='status pass';$('message').textContent='Intyg '+d.intyg_id+' utfärdat ('+d.result+') · verifieringskod '+(d.verification_code||'–')+'.'};
$('preview').onclick=async()=>{const p=$('project').value,i=$('inspection').value;const r=await fetch('/api/ovk/projects/'+encodeURIComponent(p)+'/inspections/'+encodeURIComponent(i)+'/intyg/preview',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(build())});if(!r.ok){const d=await r.json();$('message').className='status warning';$('message').textContent='Fel: '+JSON.stringify(d);return}const blob=await r.blob();window.open(URL.createObjectURL(blob),'_blank');$('message').className='status';$('message').textContent='Utkast öppnat – vattenstämplat, ej giltigt.'};
$('list').onclick=async()=>{const p=$('project').value;const r=await fetch('/api/ovk/projects/'+encodeURIComponent(p)+'/intyg');const d=await r.json();if(!r.ok){$('message').textContent='Fel: '+JSON.stringify(d);return}$('items').innerHTML='<table><tr><th>Intyg</th><th>Besiktning</th><th>Resultat</th><th>Nästa frist</th></tr>'+d.intyg.map(x=>'<tr><td>'+esc(x.intyg_id)+'</td><td>'+esc(x.inspection_id)+'</td><td>'+esc(x.result)+'</td><td>'+esc(x.next_inspection_due||'—')+'</td></tr>').join('')+'</table>'};
$('anslag').onclick=()=>{const p=$('project').value,i=$('intyg').value;window.open('/api/ovk/projects/'+encodeURIComponent(p)+'/intyg/'+encodeURIComponent(i)+'/anslag','_blank')};init();
</script></body></html>"""
