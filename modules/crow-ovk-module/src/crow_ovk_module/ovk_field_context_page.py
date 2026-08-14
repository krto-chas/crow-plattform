from __future__ import annotations

from importlib import resources

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

_UID_MARKER = "const uid = prefix => prefix + '-' + crypto.randomUUID();"
_UID_RUNTIME = """let crowUidCounter=0;
function crowRandomUuid(){
  const api=globalThis.crypto;
  if(api&&typeof api.randomUUID==='function')return api.randomUUID();
  const bytes=new Uint8Array(16);
  if(api&&typeof api.getRandomValues==='function')api.getRandomValues(bytes);
  else{
    for(let index=0;index<bytes.length;index++)bytes[index]=Math.floor(Math.random()*256);
    crowUidCounter+=1;
    bytes[0]^=crowUidCounter&255;
    bytes[1]^=(crowUidCounter>>8)&255;
  }
  bytes[6]=(bytes[6]&15)|64;
  bytes[8]=(bytes[8]&63)|128;
  const hex=[...bytes].map(value=>value.toString(16).padStart(2,'0'));
  return hex.slice(0,4).join('')+'-'+hex.slice(4,6).join('')+'-'+hex.slice(6,8).join('')+'-'+hex.slice(8,10).join('')+'-'+hex.slice(10).join('');
}
const uid=prefix=>prefix+'-'+crowRandomUuid();"""

_UNIT_KIND_MARKER = (
    "const kind=confirm('Är detta en lokal? (Avbryt = lägenhet)')?'premises':'apartment';"
)
_UNIT_KIND_RUNTIME = (
    "const type=(prompt('Typ av enhet: L = lägenhet, O = lokal','L')||'')"
    ".trim().toUpperCase();"
    "if(!type)return;"
    "if(type!=='L'&&type!=='O'){alert('Skriv L för lägenhet eller O för lokal.');return}"
    "const kind=type==='O'?'premises':'apartment';"
)

_DIGEST_MARKER = (
    "const buffer=await file.arrayBuffer();const hash=await crypto.subtle.digest('SHA-256',buffer);"
)
_SPACE_DIGEST_RUNTIME = (
    "if(!globalThis.crypto||!globalThis.crypto.subtle){"
    "$('nameplateStatus').className='status warn';"
    "$('nameplateStatus').textContent='Fotoevidens kräver HTTPS. Övrig rondering kan testas över HTTP.';"
    "$('spacePhoto').value='';return}"
    "const buffer=await file.arrayBuffer();"
    "const hash=await globalThis.crypto.subtle.digest('SHA-256',buffer);"
)
_PHOTO_DIGEST_RUNTIME = (
    "if(!globalThis.crypto||!globalThis.crypto.subtle){"
    "$('photoStatus').className='status warn';"
    "$('photoStatus').textContent='Fotoevidens kräver HTTPS. Övrig rondering kan testas över HTTP.';"
    "$('photo').value='';return}"
    "const buffer=await file.arrayBuffer();"
    "const hash=await globalThis.crypto.subtle.digest('SHA-256',buffer);"
)


def ovk_field_context_page_router() -> APIRouter:
    router = APIRouter()

    @router.get("/ovk/falt", response_class=HTMLResponse)
    def field_page() -> str:
        html = _asset_text("field.html")
        marker = '<script src="/ovk/falt/app.js"></script>'
        replacement = marker + '\n<script src="/ovk/falt/context.js"></script>'
        return html.replace(marker, replacement, 1)

    @router.get("/ovk/falt/app.js", response_class=Response)
    def field_runtime_app() -> Response:
        return Response(_field_runtime_script(), media_type="application/javascript")

    @router.get("/ovk/falt/context.js", response_class=Response)
    def field_context_app() -> Response:
        return Response(_asset_text("field-context.js"), media_type="application/javascript")

    return router


def _field_runtime_script() -> str:
    script = _asset_text("field.js")
    if _UID_MARKER not in script:
        raise RuntimeError("OVK field UID runtime marker is missing")
    if _UNIT_KIND_MARKER not in script:
        raise RuntimeError("OVK field unit-kind runtime marker is missing")
    if script.count(_DIGEST_MARKER) != 2:
        raise RuntimeError("OVK field digest runtime markers are missing")

    script = script.replace(_UID_MARKER, _UID_RUNTIME, 1)
    script = script.replace(_UNIT_KIND_MARKER, _UNIT_KIND_RUNTIME, 1)
    script = script.replace(_DIGEST_MARKER, _SPACE_DIGEST_RUNTIME, 1)
    script = script.replace(_DIGEST_MARKER, _PHOTO_DIGEST_RUNTIME, 1)
    return script


def _asset_text(name: str) -> str:
    return resources.files("crow_ovk_module").joinpath("assets", name).read_text(encoding="utf-8")
