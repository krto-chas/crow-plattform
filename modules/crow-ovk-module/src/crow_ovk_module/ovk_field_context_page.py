from __future__ import annotations

from importlib import resources

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response


def ovk_field_context_page_router() -> APIRouter:
    router = APIRouter()

    @router.get("/ovk/falt", response_class=HTMLResponse)
    def field_page() -> str:
        html = _asset_text("field.html")
        marker = '<script src="/ovk/falt/app.js"></script>'
        replacement = marker + '\n<script src="/ovk/falt/context.js"></script>'
        return html.replace(marker, replacement, 1)

    @router.get("/ovk/falt/context.js", response_class=Response)
    def field_context_app() -> Response:
        return Response(_asset_text("field-context.js"), media_type="application/javascript")

    return router


def _asset_text(name: str) -> str:
    return resources.files("crow_ovk_module").joinpath("assets", name).read_text(encoding="utf-8")
